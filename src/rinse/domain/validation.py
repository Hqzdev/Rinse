from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from statistics import median
from typing import Callable, Optional

from rinse.domain.entities import (
    ColumnTypeSuggestion,
    Dataset,
    OperationResult,
    ValidationIssue,
)
from rinse.domain.normalization import is_valid_email
from rinse.domain.operations import OperationOutcome
from rinse.domain.value_objects import CellChange, CellValue, ColumnName, RowIndex


class ColumnType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    EMPTY = "empty"


class MissingValuePolicy(str, Enum):
    KEEP = "keep"
    DROP_ROWS = "drop_rows"
    FILL = "fill"
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"


@dataclass(frozen=True)
class TypeInferenceConfig:
    columns: tuple[ColumnName, ...] = ()
    overrides: Optional[dict[str, ColumnType]] = None
    date_formats: tuple[str, ...] = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y")

    def __post_init__(self) -> None:
        if not self.date_formats:
            raise ValueError("Type inference requires at least one date format")


@dataclass(frozen=True)
class TypeInferenceOperation:
    config: TypeInferenceConfig = TypeInferenceConfig()
    name: str = "type-inference"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        suggestions = tuple(
            infer_column_type(dataset, column, self.config)
            for column in selected_columns(dataset, self.config.columns)
        )
        return OperationOutcome(
            dataset=dataset,
            result=OperationResult(name=self.name, type_suggestions=suggestions),
        )


@dataclass(frozen=True)
class MissingValueConfig:
    columns: tuple[ColumnName, ...]
    policy: MissingValuePolicy = MissingValuePolicy.KEEP
    fill_value: CellValue = None

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Missing value handling requires at least one column")
        if self.policy == MissingValuePolicy.FILL and self.fill_value is None:
            raise ValueError("Fill missing value policy requires a fill value")


@dataclass(frozen=True)
class MissingValueOperation:
    config: MissingValueConfig
    name: str = "missing-value-handling"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        if self.config.policy == MissingValuePolicy.KEEP:
            return OperationOutcome(dataset=dataset, result=OperationResult(name=self.name))
        if self.config.policy == MissingValuePolicy.DROP_ROWS:
            return drop_missing_rows(dataset, self.name, self.config.columns)
        fill_values = fill_values_for(dataset, self.config)
        return fill_missing_values(dataset, self.name, self.config.columns, fill_values)


@dataclass(frozen=True)
class RequiredValueValidationConfig:
    columns: tuple[ColumnName, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Required value validation requires at least one column")


@dataclass(frozen=True)
class RequiredValueValidationOperation:
    config: RequiredValueValidationConfig
    name: str = "required-value-validation"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return validate_dataset(
            dataset=dataset,
            name=self.name,
            columns=self.config.columns,
            validate=lambda value: "Required value is missing" if is_blank(value) else "",
            rule="required",
        )


@dataclass(frozen=True)
class NumericRangeValidationConfig:
    columns: tuple[ColumnName, ...]
    minimum: Optional[float] = None
    maximum: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Range validation requires at least one column")
        if self.minimum is None and self.maximum is None:
            raise ValueError("Range validation requires a minimum or maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Range validation minimum cannot be greater than maximum")


@dataclass(frozen=True)
class NumericRangeValidationOperation:
    config: NumericRangeValidationConfig
    name: str = "range-validation"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return validate_dataset(dataset, self.name, self.config.columns, self.validate_value, "range")

    def validate_value(self, value: CellValue) -> str:
        if is_blank(value):
            return ""
        parsed = parse_number(value)
        if parsed is None:
            return "Value is not numeric"
        if self.config.minimum is not None and parsed < self.config.minimum:
            return f"Value is below minimum {self.config.minimum:g}"
        if self.config.maximum is not None and parsed > self.config.maximum:
            return f"Value is above maximum {self.config.maximum:g}"
        return ""


@dataclass(frozen=True)
class PositiveNumberValidationConfig:
    columns: tuple[ColumnName, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Positive number validation requires at least one column")


@dataclass(frozen=True)
class PositiveNumberValidationOperation:
    config: PositiveNumberValidationConfig
    name: str = "positive-number-validation"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return validate_dataset(dataset, self.name, self.config.columns, self.validate_value, "positive_number")

    def validate_value(self, value: CellValue) -> str:
        if is_blank(value):
            return ""
        parsed = parse_number(value)
        if parsed is None:
            return "Value is not numeric"
        if parsed <= 0:
            return "Value must be positive"
        return ""


@dataclass(frozen=True)
class AllowedValuesValidationConfig:
    columns: tuple[ColumnName, ...]
    allowed_values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Allowed values validation requires at least one column")
        if not self.allowed_values:
            raise ValueError("Allowed values validation requires at least one allowed value")


@dataclass(frozen=True)
class AllowedValuesValidationOperation:
    config: AllowedValuesValidationConfig
    name: str = "allowed-values-validation"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        allowed = {value.casefold() for value in self.config.allowed_values}
        return validate_dataset(
            dataset=dataset,
            name=self.name,
            columns=self.config.columns,
            validate=lambda value: validate_allowed_value(value, allowed),
            rule="allowed_values",
        )


@dataclass(frozen=True)
class EmailValidationConfig:
    columns: tuple[ColumnName, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Email validation requires at least one column")


@dataclass(frozen=True)
class EmailValidationOperation:
    config: EmailValidationConfig
    name: str = "email-validation"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return validate_dataset(dataset, self.name, self.config.columns, validate_email_value, "valid_email")


@dataclass(frozen=True)
class DateParseabilityValidationConfig:
    columns: tuple[ColumnName, ...]
    formats: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Date parseability validation requires at least one column")
        if not self.formats:
            raise ValueError("Date parseability validation requires at least one format")


@dataclass(frozen=True)
class DateParseabilityValidationOperation:
    config: DateParseabilityValidationConfig
    name: str = "date-parseability-validation"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return validate_dataset(
            dataset=dataset,
            name=self.name,
            columns=self.config.columns,
            validate=lambda value: validate_date_value(value, self.config.formats),
            rule="parseable_date",
        )


def infer_column_type(dataset: Dataset, column: ColumnName, config: TypeInferenceConfig) -> ColumnTypeSuggestion:
    if config.overrides and column.value in config.overrides:
        return ColumnTypeSuggestion(
            column=column,
            suggested_type=config.overrides[column.value].value,
            confidence=1,
            reason="explicit override",
        )
    values = [row.get(column.value) for row in dataset.rows if not is_blank(row.get(column.value))]
    if not values:
        return ColumnTypeSuggestion(column=column, suggested_type=ColumnType.EMPTY.value, confidence=1, reason="all values are blank")
    scores = {
        ColumnType.BOOLEAN: matching_ratio(values, is_boolean),
        ColumnType.NUMBER: matching_ratio(values, lambda value: parse_number(value) is not None),
        ColumnType.DATE: matching_ratio(values, lambda value: parse_date(str(value).strip(), config.date_formats)),
    }
    suggested_type, confidence = max(scores.items(), key=lambda item: item[1])
    if confidence < 0.6:
        suggested_type = ColumnType.TEXT
        confidence = 1
    return ColumnTypeSuggestion(
        column=column,
        suggested_type=suggested_type.value,
        confidence=round(confidence, 2),
        reason=f"{len(values)} non-blank values sampled",
    )


def selected_columns(dataset: Dataset, columns: tuple[ColumnName, ...]) -> tuple[ColumnName, ...]:
    return columns or dataset.columns


def drop_missing_rows(dataset: Dataset, name: str, columns: tuple[ColumnName, ...]) -> OperationOutcome:
    rows = tuple(
        row
        for row in dataset.rows
        if not any(is_blank(row.get(column.value)) for column in columns)
    )
    return OperationOutcome(
        dataset=dataset.with_rows(rows),
        result=OperationResult(name=name, rows_removed=dataset.row_count - len(rows)),
    )


def fill_missing_values(
    dataset: Dataset,
    name: str,
    columns: tuple[ColumnName, ...],
    fill_values: dict[str, CellValue],
) -> OperationOutcome:
    rows = []
    changes = []
    for row_index, row in enumerate(dataset.rows):
        updated = dict(row)
        for column in columns:
            before = updated.get(column.value)
            if is_blank(before) and column.value in fill_values:
                after = fill_values[column.value]
                updated[column.value] = after
                changes.append(
                    CellChange(
                        row=RowIndex(row_index),
                        column=column,
                        before=before,
                        after=after,
                        reason=name,
                    )
                )
        rows.append(updated)
    return OperationOutcome(
        dataset=dataset.with_rows(tuple(rows)),
        result=OperationResult(name=name, cells_changed=tuple(changes)),
    )


def fill_values_for(dataset: Dataset, config: MissingValueConfig) -> dict[str, CellValue]:
    if config.policy == MissingValuePolicy.FILL:
        return {column.value: config.fill_value for column in config.columns}
    values = {}
    for column in config.columns:
        present_values = [row.get(column.value) for row in dataset.rows if not is_blank(row.get(column.value))]
        if config.policy == MissingValuePolicy.MODE:
            mode_value = most_common_value(present_values)
            if mode_value is not None:
                values[column.value] = mode_value
        if config.policy in (MissingValuePolicy.MEAN, MissingValuePolicy.MEDIAN):
            numbers = [parse_number(value) for value in present_values]
            numeric_values = [value for value in numbers if value is not None]
            if len(numeric_values) != len(present_values) or not numeric_values:
                raise ValueError(f"{config.policy.value} missing value policy requires numeric values in {column.value}")
            if config.policy == MissingValuePolicy.MEAN:
                values[column.value] = sum(numeric_values) / len(numeric_values)
            if config.policy == MissingValuePolicy.MEDIAN:
                values[column.value] = median(numeric_values)
    return values


def most_common_value(values: list[CellValue]) -> CellValue:
    counts = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    selected = max(counts, key=counts.get)
    for value in values:
        if str(value) == selected:
            return value
    return None


def validate_dataset(
    dataset: Dataset,
    name: str,
    columns: tuple[ColumnName, ...],
    validate: Callable[[CellValue], str],
    rule: str,
) -> OperationOutcome:
    issues = []
    for row_index, row in enumerate(dataset.rows):
        for column in columns:
            value = row.get(column.value)
            message = validate(value)
            if message:
                issues.append(
                    ValidationIssue(
                        row=RowIndex(row_index),
                        column=column,
                        rule=rule,
                        value=value,
                        message=message,
                    )
                )
    return OperationOutcome(
        dataset=dataset,
        result=OperationResult(name=name, validation_issues=tuple(issues)),
    )


def validate_allowed_value(value: CellValue, allowed: set[str]) -> str:
    if is_blank(value):
        return ""
    if str(value).casefold() not in allowed:
        return "Value is not in allowed set"
    return ""


def validate_email_value(value: CellValue) -> str:
    if is_blank(value):
        return ""
    if not is_valid_email(str(value).strip().lower()):
        return "Email is invalid"
    return ""


def validate_date_value(value: CellValue, formats: tuple[str, ...]) -> str:
    if is_blank(value):
        return ""
    if not parse_date(str(value).strip(), formats):
        return "Date could not be parsed"
    return ""


def parse_number(value: CellValue) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def parse_date(value: str, formats: tuple[str, ...]) -> bool:
    for date_format in formats:
        try:
            datetime.strptime(value, date_format)
            return True
        except ValueError:
            pass
    return False


def is_boolean(value: CellValue) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "false", "yes", "no", "1", "0"}
    return False


def matching_ratio(values: list[CellValue], predicate) -> float:
    return sum(1 for value in values if predicate(value)) / len(values)


def is_blank(value: CellValue) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False
