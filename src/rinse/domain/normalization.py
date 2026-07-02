from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re
from typing import Callable, Mapping, Optional, Protocol

from rinse.domain.entities import Dataset, OperationResult, ValidationIssue
from rinse.domain.operations import OperationOutcome
from rinse.domain.value_objects import CellChange, CellValue, ColumnName, RowIndex


class TextCase(str, Enum):
    KEEP = "keep"
    LOWER = "lower"
    UPPER = "upper"
    TITLE = "title"


class PhoneNumberNormalizer(Protocol):
    def normalize(self, value: str, default_region: str) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class TextNormalizationConfig:
    columns: tuple[ColumnName, ...]
    case: TextCase = TextCase.KEEP

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Text normalization requires at least one column")


@dataclass(frozen=True)
class EmailNormalizationConfig:
    columns: tuple[ColumnName, ...]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Email normalization requires at least one column")


@dataclass(frozen=True)
class DateNormalizationConfig:
    columns: tuple[ColumnName, ...]
    input_formats: tuple[str, ...]
    output_format: str

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Date normalization requires at least one column")
        if not self.input_formats:
            raise ValueError("Date normalization requires at least one input format")
        if not self.output_format.strip():
            raise ValueError("Date normalization output format cannot be empty")


@dataclass(frozen=True)
class PhoneNormalizationConfig:
    columns: tuple[ColumnName, ...]
    default_region: str

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Phone normalization requires at least one column")
        if not self.default_region.strip():
            raise ValueError("Phone normalization requires a default region")


@dataclass(frozen=True)
class TextNormalizationOperation:
    config: TextNormalizationConfig
    name: str = "text-normalization"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return normalize_rows(dataset, self.name, self.config.columns, self.normalize_value)

    def normalize_value(self, value: CellValue) -> tuple[CellValue, Optional["ValidationIssueFactory"]]:
        if not isinstance(value, str):
            return value, None
        normalized = " ".join(value.strip().split())
        if self.config.case == TextCase.LOWER:
            normalized = normalized.lower()
        if self.config.case == TextCase.UPPER:
            normalized = normalized.upper()
        if self.config.case == TextCase.TITLE:
            normalized = normalized.title()
        return normalized, None


@dataclass(frozen=True)
class EmailNormalizationOperation:
    config: EmailNormalizationConfig
    name: str = "email-normalization"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return normalize_rows(dataset, self.name, self.config.columns, self.normalize_value)

    def normalize_value(self, value: CellValue) -> tuple[CellValue, Optional["ValidationIssueFactory"]]:
        if value is None:
            return value, None
        normalized = str(value).strip().lower()
        if not normalized:
            return None, None
        if not is_valid_email(normalized):
            return normalized, ValidationIssueFactory("valid_email", "Email is invalid")
        return normalized, None


@dataclass(frozen=True)
class DateNormalizationOperation:
    config: DateNormalizationConfig
    name: str = "date-normalization"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return normalize_rows(dataset, self.name, self.config.columns, self.normalize_value)

    def normalize_value(self, value: CellValue) -> tuple[CellValue, Optional["ValidationIssueFactory"]]:
        if value is None:
            return value, None
        raw = str(value).strip()
        if not raw:
            return None, None
        parsed = parse_date(raw, self.config.input_formats)
        if parsed is None:
            return raw, ValidationIssueFactory("parseable_date", "Date could not be parsed")
        return parsed.strftime(self.config.output_format), None


@dataclass(frozen=True)
class PhoneNormalizationOperation:
    config: PhoneNormalizationConfig
    normalizer: PhoneNumberNormalizer
    name: str = "phone-normalization"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return normalize_rows(dataset, self.name, self.config.columns, self.normalize_value)

    def normalize_value(self, value: CellValue) -> tuple[CellValue, Optional["ValidationIssueFactory"]]:
        if value is None:
            return value, None
        raw = str(value).strip()
        if not raw:
            return None, None
        try:
            return self.normalizer.normalize(raw, self.config.default_region), None
        except ValueError:
            return raw, ValidationIssueFactory("valid_phone", "Phone number is invalid")


@dataclass(frozen=True)
class ValidationIssueFactory:
    rule: str
    message: str

    def create(self, row: RowIndex, column: ColumnName, value: CellValue) -> ValidationIssue:
        return ValidationIssue(
            row=row,
            column=column,
            rule=self.rule,
            value=value,
            message=self.message,
        )


def normalize_rows(
    dataset: Dataset,
    name: str,
    columns: tuple[ColumnName, ...],
    normalize: Callable[[CellValue], tuple[CellValue, Optional[ValidationIssueFactory]]],
) -> OperationOutcome:
    rows: list[Mapping[str, CellValue]] = []
    changes: list[CellChange] = []
    issues: list[ValidationIssue] = []
    for row_index, row in enumerate(dataset.rows):
        updated = dict(row)
        for column in columns:
            before = updated.get(column.value)
            after, issue_factory = normalize(before)
            if before != after:
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
            if issue_factory is not None:
                issues.append(issue_factory.create(RowIndex(row_index), column, after))
        rows.append(updated)
    return OperationOutcome(
        dataset=dataset.with_rows(tuple(rows)),
        result=OperationResult(
            name=name,
            cells_changed=tuple(changes),
            validation_issues=tuple(issues),
        ),
    )


def is_valid_email(value: str) -> bool:
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value) is not None


def parse_date(value: str, formats: tuple[str, ...]) -> Optional[datetime]:
    for date_format in formats:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            pass
    return None
