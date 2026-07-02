from pathlib import Path
from typing import Optional

import typer

from rinse.adapters import PandasDatasetReader, PandasDatasetWriter, PhoneNumbersNormalizer, RapidFuzzTextSimilarity
from rinse.adapters.dataset_files import DatasetFileError, UnsupportedDatasetFormatError
from rinse.application import CleaningPipeline, CleaningPipelineRequest, ProfileDataset, ProfileDatasetRequest
from rinse.domain import (
    ColumnName,
    DateNormalizationConfig,
    DateNormalizationOperation,
    DeduplicationConfig,
    DeduplicationMode,
    EmailNormalizationConfig,
    EmailNormalizationOperation,
    ExactDeduplicationOperation,
    FuzzyDeduplicationConfig,
    FuzzyDeduplicationOperation,
    PhoneNormalizationConfig,
    PhoneNormalizationOperation,
    TextCase,
    TextNormalizationConfig,
    TextNormalizationOperation,
)
from rinse.domain.operations import CleaningOperation
from rinse.domain.value_objects import DatasetReference

app = typer.Typer(help="Clean messy CSV and Excel files.")


@app.command()
def profile(input_path: str) -> None:
    try:
        result = ProfileDataset(PandasDatasetReader()).execute(
            ProfileDatasetRequest(DatasetReference(input_path))
        )
    except (DatasetFileError, UnsupportedDatasetFormatError, ValueError) as error:
        raise typer.BadParameter(str(error))
    typer.echo(f"rows: {result.rows}")
    typer.echo(f"columns: {result.columns}")
    typer.echo(f"column_names: {', '.join(result.column_names)}")


@app.command()
def clean(
    input_path: str,
    out: str = typer.Option(..., "--out", "-o"),
    dedup: str = typer.Option("none", "--dedup"),
    dedup_columns: str = typer.Option("", "--dedup-columns"),
    fuzzy_threshold: float = typer.Option(92, "--fuzzy-threshold"),
    fuzzy_mode: str = typer.Option("suggest", "--fuzzy-mode"),
    normalize: str = typer.Option("", "--normalize"),
    normalize_columns: str = typer.Option("", "--normalize-columns"),
    text_columns: str = typer.Option("", "--text-columns"),
    email_columns: str = typer.Option("", "--email-columns"),
    date_columns: str = typer.Option("", "--date-columns"),
    phone_columns: str = typer.Option("", "--phone-columns"),
    text_case: str = typer.Option("keep", "--text-case"),
    date_input_format: str = typer.Option("%m/%d/%Y", "--date-input-format"),
    date_output_format: str = typer.Option("%Y-%m-%d", "--date-output-format"),
    phone_region: str = typer.Option("US", "--phone-region"),
) -> None:
    try:
        reader = PandasDatasetReader()
        writer = PandasDatasetWriter()
        dataset = reader.read(DatasetReference(input_path))
        operations = build_operations(
            dedup=dedup,
            dedup_columns=dedup_columns,
            fuzzy_threshold=fuzzy_threshold,
            fuzzy_mode=fuzzy_mode,
            normalize=normalize,
            normalize_columns=normalize_columns,
            text_columns=text_columns,
            email_columns=email_columns,
            date_columns=date_columns,
            phone_columns=phone_columns,
            text_case=text_case,
            date_input_format=date_input_format,
            date_output_format=date_output_format,
            phone_region=phone_region,
        )
        cleaned = dataset
        report = None
        if operations:
            result = CleaningPipeline(tuple(operations)).run(CleaningPipelineRequest(dataset=dataset))
            cleaned = result.dataset
            report = result.report
        writer.write(cleaned, DatasetReference(out))
    except (DatasetFileError, UnsupportedDatasetFormatError, ValueError) as error:
        raise typer.BadParameter(str(error))
    typer.echo(f"output: {out}")
    typer.echo(f"rows_before: {dataset.row_count}")
    typer.echo(f"rows_after: {cleaned.row_count}")
    if report is not None:
        typer.echo(f"rows_removed: {report.rows_removed}")
        typer.echo(f"cells_changed: {report.cells_changed}")
        typer.echo(f"validation_issues: {report.validation_issue_count}")
        typer.echo(f"duplicate_groups: {report.duplicate_group_count}")


def build_operations(
    dedup: str,
    dedup_columns: str,
    fuzzy_threshold: float,
    fuzzy_mode: str,
    normalize: str,
    normalize_columns: str,
    text_columns: str,
    email_columns: str,
    date_columns: str,
    phone_columns: str,
    text_case: str,
    date_input_format: str,
    date_output_format: str,
    phone_region: str,
) -> list[CleaningOperation]:
    operations: list[CleaningOperation] = []
    fallback_columns = parse_columns(normalize_columns)
    for name in parse_names(normalize):
        operations.append(
            build_normalization_operation(
                name=name,
                columns=normalization_columns_for(
                    name=name,
                    fallback_columns=fallback_columns,
                    text_columns=text_columns,
                    email_columns=email_columns,
                    date_columns=date_columns,
                    phone_columns=phone_columns,
                ),
                text_case=text_case,
                date_input_format=date_input_format,
                date_output_format=date_output_format,
                phone_region=phone_region,
            )
        )
    dedup_name = dedup.strip().casefold()
    if dedup_name == "none":
        return operations
    columns = parse_columns(dedup_columns)
    if dedup_name == "exact":
        operations.append(ExactDeduplicationOperation(config=DeduplicationConfig(columns=columns)))
        return operations
    if dedup_name == "fuzzy":
        operations.append(
            FuzzyDeduplicationOperation(
                config=FuzzyDeduplicationConfig(
                    columns=required_columns(columns, "Fuzzy deduplication requires --dedup-columns"),
                    threshold=fuzzy_threshold,
                    mode=DeduplicationMode(fuzzy_mode),
                ),
                similarity=RapidFuzzTextSimilarity(),
            )
        )
        return operations
    raise ValueError(f"Unsupported deduplication mode: {dedup}")


def normalization_columns_for(
    name: str,
    fallback_columns: tuple[ColumnName, ...],
    text_columns: str,
    email_columns: str,
    date_columns: str,
    phone_columns: str,
) -> tuple[ColumnName, ...]:
    if name == "text":
        return parse_columns(text_columns) or fallback_columns
    if name == "email":
        return parse_columns(email_columns) or fallback_columns
    if name == "date":
        return parse_columns(date_columns) or fallback_columns
    if name == "phone":
        return parse_columns(phone_columns) or fallback_columns
    return fallback_columns


def build_normalization_operation(
    name: str,
    columns: tuple[ColumnName, ...],
    text_case: str,
    date_input_format: str,
    date_output_format: str,
    phone_region: str,
) -> CleaningOperation:
    selected = required_columns(columns, f"{name} normalization requires --normalize-columns")
    if name == "text":
        return TextNormalizationOperation(
            config=TextNormalizationConfig(columns=selected, case=TextCase(text_case))
        )
    if name == "email":
        return EmailNormalizationOperation(config=EmailNormalizationConfig(columns=selected))
    if name == "date":
        return DateNormalizationOperation(
            config=DateNormalizationConfig(
                columns=selected,
                input_formats=tuple(parse_names(date_input_format)),
                output_format=date_output_format,
            )
        )
    if name == "phone":
        return PhoneNormalizationOperation(
            config=PhoneNormalizationConfig(columns=selected, default_region=phone_region),
            normalizer=PhoneNumbersNormalizer(),
        )
    raise ValueError(f"Unsupported normalization operation: {name}")


def parse_columns(value: str) -> tuple[ColumnName, ...]:
    return tuple(ColumnName(name) for name in parse_names(value))


def required_columns(columns: tuple[ColumnName, ...], message: str) -> tuple[ColumnName, ...]:
    if not columns:
        raise ValueError(message)
    return columns


def parse_names(value: str) -> list[str]:
    return [name.strip() for name in value.split(",") if name.strip()]


def cli_main(args: Optional[list[str]] = None) -> None:
    app(args=args)


if __name__ == "__main__":
    cli_main()
