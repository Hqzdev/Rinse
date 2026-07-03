from dataclasses import dataclass, field
from typing import Mapping

from rinse.domain.value_objects import CellChange, CellValue, ColumnName, RowIndex


@dataclass(frozen=True)
class Dataset:
    columns: tuple[ColumnName, ...]
    rows: tuple[Mapping[str, CellValue], ...]

    def __post_init__(self) -> None:
        names = [column.value for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Dataset columns must be unique")
        object.__setattr__(self, "rows", tuple(dict(row) for row in self.rows))

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return len(self.columns)

    def with_rows(self, rows: tuple[Mapping[str, CellValue], ...]) -> "Dataset":
        return Dataset(columns=self.columns, rows=rows)


@dataclass(frozen=True)
class ValidationIssue:
    row: RowIndex
    column: ColumnName
    rule: str
    value: CellValue
    message: str

    def __post_init__(self) -> None:
        if not self.rule.strip():
            raise ValueError("Validation rule cannot be empty")
        if not self.message.strip():
            raise ValueError("Validation message cannot be empty")


@dataclass(frozen=True)
class DuplicateGroup:
    kept_row: RowIndex
    matched_rows: tuple[RowIndex, ...]
    score: float
    reason: str

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("Duplicate score must be between 0 and 100")
        if not self.matched_rows:
            raise ValueError("Duplicate group must contain at least one matched row")
        if not self.reason.strip():
            raise ValueError("Duplicate reason cannot be empty")


@dataclass(frozen=True)
class OperationResult:
    name: str
    rows_removed: int = 0
    cells_changed: tuple[CellChange, ...] = field(default_factory=tuple)
    validation_issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    duplicate_groups: tuple[DuplicateGroup, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Operation name cannot be empty")
        if self.rows_removed < 0:
            raise ValueError("Rows removed cannot be negative")


@dataclass(frozen=True)
class CleaningReport:
    rows_before: int
    rows_after: int
    operation_results: tuple[OperationResult, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.rows_before < 0:
            raise ValueError("Rows before cannot be negative")
        if self.rows_after < 0:
            raise ValueError("Rows after cannot be negative")

    @property
    def rows_removed(self) -> int:
        return self.rows_before - self.rows_after

    @property
    def cells_changed(self) -> int:
        return sum(len(result.cells_changed) for result in self.operation_results)

    @property
    def validation_issue_count(self) -> int:
        return sum(len(result.validation_issues) for result in self.operation_results)

    @property
    def duplicate_group_count(self) -> int:
        return sum(len(result.duplicate_groups) for result in self.operation_results)

    def to_dict(self) -> dict[str, object]:
        return {
            "rows_before": self.rows_before,
            "rows_after": self.rows_after,
            "rows_removed": self.rows_removed,
            "cells_changed": self.cells_changed,
            "validation_issue_count": self.validation_issue_count,
            "duplicate_group_count": self.duplicate_group_count,
            "operations": [
                {
                    "name": result.name,
                    "rows_removed": result.rows_removed,
                    "cells_changed": len(result.cells_changed),
                    "validation_issues": len(result.validation_issues),
                    "duplicate_groups": len(result.duplicate_groups),
                    "cell_changes": [
                        {
                            "row": change.row.value,
                            "column": change.column.value,
                            "before": change.before,
                            "after": change.after,
                            "reason": change.reason,
                        }
                        for change in result.cells_changed
                    ],
                    "issues": [
                        {
                            "row": issue.row.value,
                            "column": issue.column.value,
                            "rule": issue.rule,
                            "value": issue.value,
                            "message": issue.message,
                        }
                        for issue in result.validation_issues
                    ],
                    "duplicates": [
                        {
                            "kept_row": group.kept_row.value,
                            "matched_rows": [row.value for row in group.matched_rows],
                            "score": group.score,
                            "reason": group.reason,
                        }
                        for group in result.duplicate_groups
                    ],
                }
                for result in self.operation_results
            ],
        }
