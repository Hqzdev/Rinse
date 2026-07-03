from pathlib import Path
from typing import Optional

import typer

from rinse.adapters import (
    JsonReportWriter,
    PandasDatasetReader,
    PandasDatasetWriter,
    PhoneNumbersNormalizer,
    RapidFuzzTextSimilarity,
)
from rinse.adapters.dataset_files import DatasetFileError, UnsupportedDatasetFormatError
from rinse.application import CleaningPipeline, CleaningPipelineRequest, ProfileDataset, ProfileDatasetRequest
from rinse.domain import (
    AllowedValuesValidationConfig,
    AllowedValuesValidationOperation,
    CleaningReport,
    ColumnType,
    ColumnName,
    DateNormalizationConfig,
    DateNormalizationOperation,
    DateParseabilityValidationConfig,
    DateParseabilityValidationOperation,
    DeduplicationConfig,
    DeduplicationMode,
    EmailNormalizationConfig,
    EmailNormalizationOperation,
    EmailValidationConfig,
    EmailValidationOperation,
    ExactDeduplicationOperation,
    FuzzyDeduplicationConfig,
    FuzzyDeduplicationOperation,
    MissingValueConfig,
    MissingValueOperation,
    MissingValuePolicy,
    NumericRangeValidationConfig,
    NumericRangeValidationOperation,
    PhoneNormalizationConfig,
    PhoneNormalizationOperation,
    PositiveNumberValidationConfig,
    PositiveNumberValidationOperation,
    RequiredValueValidationConfig,
    RequiredValueValidationOperation,
    TextCase,
    TextNormalizationConfig,
    TextNormalizationOperation,
    TypeInferenceConfig,
    TypeInferenceOperation,
)
from rinse.domain.operations import CleaningOperation
from rinse.domain.value_objects import CellValue, DatasetReference

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
    report_path: str = typer.Option("", "--report"),
    dedup: str = typer.Option("none", "--dedup"),
    dedup_columns: str = typer.Option("", "--dedup-columns"),
    fuzzy_threshold: float = typer.Option(92, "--fuzzy-threshold"),
    fuzzy_mode: str = typer.Option("suggest", "--fuzzy-mode"),
    infer_types: bool = typer.Option(False, "--infer-types"),
    type_columns: str = typer.Option("", "--type-columns"),
    type_overrides: str = typer.Option("", "--type-overrides"),
    missing_policy: str = typer.Option("keep", "--missing-policy"),
    missing_columns: str = typer.Option("", "--missing-columns"),
    fill_value: str = typer.Option("", "--fill-value"),
    validate: str = typer.Option("", "--validate"),
    required_columns: str = typer.Option("", "--required-columns"),
    range_columns: str = typer.Option("", "--range-columns"),
    min_value: Optional[float] = typer.Option(None, "--min-value"),
    max_value: Optional[float] = typer.Option(None, "--max-value"),
    positive_columns: str = typer.Option("", "--positive-columns"),
    allowed_columns: str = typer.Option("", "--allowed-columns"),
    allowed_values: str = typer.Option("", "--allowed-values"),
    valid_email_columns: str = typer.Option("", "--valid-email-columns"),
    parseable_date_columns: str = typer.Option("", "--parseable-date-columns"),
    validation_date_format: str = typer.Option("%Y-%m-%d,%m/%d/%Y", "--validation-date-format"),
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
            infer_types=infer_types,
            type_columns=type_columns,
            type_overrides=type_overrides,
            missing_policy=missing_policy,
            missing_columns=missing_columns,
            fill_value=fill_value,
            validate=validate,
            required_columns=required_columns,
            range_columns=range_columns,
            min_value=min_value,
            max_value=max_value,
            positive_columns=positive_columns,
            allowed_columns=allowed_columns,
            allowed_values=allowed_values,
            valid_email_columns=valid_email_columns,
            parseable_date_columns=parseable_date_columns,
            validation_date_format=validation_date_format,
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
        cleaning_report = None
        if operations:
            result = CleaningPipeline(tuple(operations)).run(CleaningPipelineRequest(dataset=dataset))
            cleaned = result.dataset
            cleaning_report = result.report
        elif report_path:
            cleaning_report = CleaningReport(rows_before=dataset.row_count, rows_after=cleaned.row_count)
        writer.write(cleaned, DatasetReference(out))
        if cleaning_report is not None and report_path:
            JsonReportWriter().write(cleaning_report, DatasetReference(report_path))
    except (DatasetFileError, UnsupportedDatasetFormatError, ValueError) as error:
        raise typer.BadParameter(str(error))
    typer.echo(f"output: {out}")
    typer.echo(f"rows_before: {dataset.row_count}")
    typer.echo(f"rows_after: {cleaned.row_count}")
    if cleaning_report is not None:
        typer.echo(f"rows_removed: {cleaning_report.rows_removed}")
        typer.echo(f"cells_changed: {cleaning_report.cells_changed}")
        typer.echo(f"validation_issues: {cleaning_report.validation_issue_count}")
        typer.echo(f"duplicate_groups: {cleaning_report.duplicate_group_count}")
        if report_path:
            typer.echo(f"report: {report_path}")


def build_operations(
    dedup: str,
    dedup_columns: str,
    fuzzy_threshold: float,
    fuzzy_mode: str,
    infer_types: bool,
    type_columns: str,
    type_overrides: str,
    missing_policy: str,
    missing_columns: str,
    fill_value: str,
    validate: str,
    required_columns: str,
    range_columns: str,
    min_value: Optional[float],
    max_value: Optional[float],
    positive_columns: str,
    allowed_columns: str,
    allowed_values: str,
    valid_email_columns: str,
    parseable_date_columns: str,
    validation_date_format: str,
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
    if infer_types:
        operations.append(
            TypeInferenceOperation(
                config=TypeInferenceConfig(
                    columns=parse_columns(type_columns),
                    overrides=parse_type_overrides(type_overrides),
                )
            )
        )
    missing_operation = build_missing_value_operation(
        missing_policy=missing_policy,
        missing_columns=missing_columns,
        fill_value=fill_value,
    )
    if missing_operation is not None:
        operations.append(missing_operation)
    for name in parse_names(validate):
        operations.append(
            build_validation_operation(
                name=name,
                required_columns=required_columns,
                range_columns=range_columns,
                min_value=min_value,
                max_value=max_value,
                positive_columns=positive_columns,
                allowed_columns=allowed_columns,
                allowed_values=allowed_values,
                valid_email_columns=valid_email_columns,
                parseable_date_columns=parseable_date_columns,
                validation_date_format=validation_date_format,
            )
        )
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
                    columns=ensure_columns(columns, "Fuzzy deduplication requires --dedup-columns"),
                    threshold=fuzzy_threshold,
                    mode=DeduplicationMode(fuzzy_mode),
                ),
                similarity=RapidFuzzTextSimilarity(),
            )
        )
        return operations
    raise ValueError(f"Unsupported deduplication mode: {dedup}")


def build_missing_value_operation(
    missing_policy: str,
    missing_columns: str,
    fill_value: str,
) -> Optional[CleaningOperation]:
    policy = MissingValuePolicy(missing_policy.strip().casefold())
    if policy == MissingValuePolicy.KEEP:
        return None
    return MissingValueOperation(
        config=MissingValueConfig(
            columns=ensure_columns(parse_columns(missing_columns), f"{policy.value} missing value policy requires --missing-columns"),
            policy=policy,
            fill_value=parse_cell_value(fill_value),
        )
    )


def build_validation_operation(
    name: str,
    required_columns: str,
    range_columns: str,
    min_value: Optional[float],
    max_value: Optional[float],
    positive_columns: str,
    allowed_columns: str,
    allowed_values: str,
    valid_email_columns: str,
    parseable_date_columns: str,
    validation_date_format: str,
) -> CleaningOperation:
    if name == "required":
        return RequiredValueValidationOperation(
            config=RequiredValueValidationConfig(
                columns=required_columns_for_validation(required_columns)
            )
        )
    if name == "range":
        return NumericRangeValidationOperation(
            config=NumericRangeValidationConfig(
                columns=ensure_columns(parse_columns(range_columns), "Range validation requires --range-columns"),
                minimum=min_value,
                maximum=max_value,
            )
        )
    if name == "positive":
        return PositiveNumberValidationOperation(
            config=PositiveNumberValidationConfig(
                columns=ensure_columns(parse_columns(positive_columns), "Positive validation requires --positive-columns")
            )
        )
    if name == "allowed":
        return AllowedValuesValidationOperation(
            config=AllowedValuesValidationConfig(
                columns=ensure_columns(parse_columns(allowed_columns), "Allowed values validation requires --allowed-columns"),
                allowed_values=tuple(parse_names(allowed_values)),
            )
        )
    if name == "email":
        return EmailValidationOperation(
            config=EmailValidationConfig(
                columns=ensure_columns(parse_columns(valid_email_columns), "Email validation requires --valid-email-columns")
            )
        )
    if name == "date":
        return DateParseabilityValidationOperation(
            config=DateParseabilityValidationConfig(
                columns=ensure_columns(parse_columns(parseable_date_columns), "Date validation requires --parseable-date-columns"),
                formats=tuple(parse_names(validation_date_format)),
            )
        )
    raise ValueError(f"Unsupported validation operation: {name}")


def required_columns_for_validation(value: str) -> tuple[ColumnName, ...]:
    return ensure_columns(parse_columns(value), "Required value validation requires --required-columns")


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
    selected = ensure_columns(columns, f"{name} normalization requires --normalize-columns")
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


def parse_type_overrides(value: str) -> dict[str, ColumnType]:
    overrides = {}
    for item in parse_names(value):
        if ":" not in item:
            raise ValueError("Type overrides must use column:type entries")
        column, column_type = item.split(":", 1)
        overrides[ColumnName(column).value] = ColumnType(column_type.strip().casefold())
    return overrides


def parse_cell_value(value: str) -> CellValue:
    if not value:
        return None
    return value


def ensure_columns(columns: tuple[ColumnName, ...], message: str) -> tuple[ColumnName, ...]:
    if not columns:
        raise ValueError(message)
    return columns


def parse_names(value: str) -> list[str]:
    return [name.strip() for name in value.split(",") if name.strip()]


def cli_main(args: Optional[list[str]] = None) -> None:
    app(args=args)


if __name__ == "__main__":
    cli_main()
