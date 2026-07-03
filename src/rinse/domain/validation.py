from dataclasses import dataclass

from rinse.domain.entities import Dataset, OperationResult, ValidationIssue
from rinse.domain.operations import OperationOutcome
from rinse.domain.value_objects import CellValue, ColumnName, RowIndex


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
        issues: list[ValidationIssue] = []
        for row_index, row in enumerate(dataset.rows):
            for column in self.config.columns:
                value = row.get(column.value)
                if is_blank(value):
                    issues.append(
                        ValidationIssue(
                            row=RowIndex(row_index),
                            column=column,
                            rule="required",
                            value=value,
                            message="Required value is missing",
                        )
                    )
        return OperationOutcome(
            dataset=dataset,
            result=OperationResult(name=self.name, validation_issues=tuple(issues)),
        )


def is_blank(value: CellValue) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False
