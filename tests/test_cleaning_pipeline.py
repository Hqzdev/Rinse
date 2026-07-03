import unittest
from dataclasses import dataclass

from rinse.application import CleaningPipeline, CleaningPipelineRequest
from rinse.domain import (
    CellChange,
    ColumnName,
    Dataset,
    OperationOutcome,
    OperationResult,
    RowIndex,
    ValidationIssue,
)


def sample_dataset() -> Dataset:
    return Dataset(
        columns=(ColumnName("name"), ColumnName("email")),
        rows=(
            {"name": " Alice ", "email": "alice@example.com"},
            {"name": "Bob", "email": ""},
        ),
    )


@dataclass(frozen=True)
class RenameFirstCellOperation:
    name: str = "rename-first-cell"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        rows = tuple(dict(row) for row in dataset.rows)
        updated_first_row = dict(rows[0])
        updated_first_row["name"] = "Alice"
        updated_rows = (updated_first_row,) + rows[1:]
        return OperationOutcome(
            dataset=dataset.with_rows(updated_rows),
            result=OperationResult(
                name=self.name,
                cells_changed=(
                    CellChange(
                        row=RowIndex(0),
                        column=ColumnName("name"),
                        before=" Alice ",
                        after="Alice",
                        reason="trimmed whitespace",
                    ),
                ),
            ),
        )


@dataclass(frozen=True)
class RemoveBlankEmailOperation:
    name: str = "remove-blank-email"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        kept_rows = tuple(row for row in dataset.rows if row["email"])
        return OperationOutcome(
            dataset=dataset.with_rows(kept_rows),
            result=OperationResult(name=self.name, rows_removed=dataset.row_count - len(kept_rows)),
        )


@dataclass(frozen=True)
class FlagValidationIssueOperation:
    name: str = "flag-validation-issue"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        return OperationOutcome(
            dataset=dataset,
            result=OperationResult(
                name=self.name,
                validation_issues=(
                    ValidationIssue(
                        row=RowIndex(0),
                        column=ColumnName("email"),
                        rule="valid_email",
                        value="alice@example.com",
                        message="Email is valid",
                    ),
                ),
            ),
        )


class CleaningPipelineTests(unittest.TestCase):
    def test_runs_operations_in_order_and_aggregates_report(self) -> None:
        pipeline = CleaningPipeline(
            operations=(
                RenameFirstCellOperation(),
                RemoveBlankEmailOperation(),
                FlagValidationIssueOperation(),
            )
        )
        result = pipeline.run(CleaningPipelineRequest(dataset=sample_dataset()))
        self.assertEqual(result.dataset.row_count, 1)
        self.assertEqual(result.dataset.rows[0]["name"], "Alice")
        self.assertEqual(result.report.rows_before, 2)
        self.assertEqual(result.report.rows_after, 1)
        self.assertEqual(result.report.rows_removed, 1)
        self.assertEqual(result.report.cells_changed, 1)
        self.assertEqual(result.report.validation_issue_count, 1)
        self.assertEqual(
            [operation.name for operation in result.report.operation_results],
            ["rename-first-cell", "remove-blank-email", "flag-validation-issue"],
        )

    def test_report_is_machine_readable(self) -> None:
        pipeline = CleaningPipeline(operations=(RenameFirstCellOperation(),))
        result = pipeline.run(CleaningPipelineRequest(dataset=sample_dataset(), preview=True))
        self.assertTrue(result.preview)
        self.assertEqual(
            result.report.to_dict(),
            {
                "rows_before": 2,
                "rows_after": 2,
                "rows_removed": 0,
                "cells_changed": 1,
                "validation_issue_count": 0,
                "duplicate_group_count": 0,
                "operations": [
                    {
                        "name": "rename-first-cell",
                        "rows_removed": 0,
                        "cells_changed": 1,
                        "validation_issues": 0,
                        "duplicate_groups": 0,
                        "type_suggestions": [],
                        "cell_changes": [
                            {
                                "row": 0,
                                "column": "name",
                                "before": " Alice ",
                                "after": "Alice",
                                "reason": "trimmed whitespace",
                            }
                        ],
                        "issues": [],
                        "duplicates": [],
                    }
                ],
            },
        )

    def test_rejects_empty_pipeline(self) -> None:
        with self.assertRaises(ValueError):
            CleaningPipeline(operations=())

    def test_rejects_duplicate_operation_names(self) -> None:
        with self.assertRaises(ValueError):
            CleaningPipeline(operations=(RenameFirstCellOperation(), RenameFirstCellOperation()))


if __name__ == "__main__":
    unittest.main()
