import unittest

from rinse.domain import (
    ColumnName,
    Dataset,
    RequiredValueValidationConfig,
    RequiredValueValidationOperation,
)


class ValidationOperationTests(unittest.TestCase):
    def test_reports_missing_required_values_without_mutating_rows(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("name"), ColumnName("email")),
            rows=(
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": ""},
                {"name": "", "email": None},
            ),
        )
        operation = RequiredValueValidationOperation(
            config=RequiredValueValidationConfig(columns=(ColumnName("name"), ColumnName("email")))
        )
        result = operation.apply(dataset)
        self.assertEqual(result.dataset.rows, dataset.rows)
        self.assertEqual(len(result.result.validation_issues), 3)
        self.assertEqual(result.result.validation_issues[0].rule, "required")
        self.assertEqual(result.result.validation_issues[0].column, ColumnName("email"))

    def test_requires_columns(self) -> None:
        with self.assertRaises(ValueError):
            RequiredValueValidationConfig(columns=())


if __name__ == "__main__":
    unittest.main()
