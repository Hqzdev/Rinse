import unittest

from rinse.domain import (
    AllowedValuesValidationConfig,
    AllowedValuesValidationOperation,
    ColumnName,
    ColumnType,
    DateParseabilityValidationConfig,
    DateParseabilityValidationOperation,
    Dataset,
    EmailValidationConfig,
    EmailValidationOperation,
    MissingValueConfig,
    MissingValueOperation,
    MissingValuePolicy,
    NumericRangeValidationConfig,
    NumericRangeValidationOperation,
    PositiveNumberValidationConfig,
    PositiveNumberValidationOperation,
    RequiredValueValidationConfig,
    RequiredValueValidationOperation,
    TypeInferenceConfig,
    TypeInferenceOperation,
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

    def test_infers_column_types_as_report_suggestions(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("age"), ColumnName("signup_date"), ColumnName("name")),
            rows=(
                {"age": "10", "signup_date": "2026-01-02", "name": "Alice"},
                {"age": "20", "signup_date": "2026-02-03", "name": "Bob"},
                {"age": "", "signup_date": "", "name": "Carla"},
            ),
        )
        operation = TypeInferenceOperation(config=TypeInferenceConfig())
        result = operation.apply(dataset)
        suggestions = {
            suggestion.column.value: suggestion.suggested_type
            for suggestion in result.result.type_suggestions
        }
        self.assertEqual(suggestions["age"], "number")
        self.assertEqual(suggestions["signup_date"], "date")
        self.assertEqual(suggestions["name"], "text")
        self.assertEqual(result.dataset.rows, dataset.rows)

    def test_type_overrides_are_reported_as_suggestions(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("customer_id"),),
            rows=({"customer_id": "001"}, {"customer_id": "002"}),
        )
        operation = TypeInferenceOperation(
            config=TypeInferenceConfig(overrides={"customer_id": ColumnType.TEXT})
        )
        result = operation.apply(dataset)
        suggestion = result.result.type_suggestions[0]
        self.assertEqual(suggestion.suggested_type, "text")
        self.assertEqual(suggestion.reason, "explicit override")

    def test_fills_missing_values_and_reports_cell_changes(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("name"), ColumnName("score")),
            rows=(
                {"name": "Alice", "score": "10"},
                {"name": "Bob", "score": ""},
                {"name": "Carla", "score": None},
            ),
        )
        operation = MissingValueOperation(
            config=MissingValueConfig(
                columns=(ColumnName("score"),),
                policy=MissingValuePolicy.MEAN,
            )
        )
        result = operation.apply(dataset)
        self.assertEqual(result.dataset.rows[1]["score"], 10)
        self.assertEqual(result.dataset.rows[2]["score"], 10)
        self.assertEqual(len(result.result.cells_changed), 2)

    def test_drops_rows_with_missing_values(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("name"), ColumnName("email")),
            rows=(
                {"name": "Alice", "email": "alice@example.com"},
                {"name": "Bob", "email": ""},
            ),
        )
        operation = MissingValueOperation(
            config=MissingValueConfig(
                columns=(ColumnName("email"),),
                policy=MissingValuePolicy.DROP_ROWS,
            )
        )
        result = operation.apply(dataset)
        self.assertEqual(result.dataset.row_count, 1)
        self.assertEqual(result.result.rows_removed, 1)

    def test_reports_bad_numeric_and_range_values(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("amount"),),
            rows=({"amount": "10"}, {"amount": "-1"}, {"amount": "broken"}, {"amount": "101"}),
        )
        operation = NumericRangeValidationOperation(
            config=NumericRangeValidationConfig(
                columns=(ColumnName("amount"),),
                minimum=0,
                maximum=100,
            )
        )
        result = operation.apply(dataset)
        self.assertEqual(len(result.result.validation_issues), 3)
        self.assertEqual(result.result.validation_issues[0].rule, "range")

    def test_reports_non_positive_numbers(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("amount"),),
            rows=({"amount": "1"}, {"amount": "0"}, {"amount": "-5"}),
        )
        operation = PositiveNumberValidationOperation(
            config=PositiveNumberValidationConfig(columns=(ColumnName("amount"),))
        )
        result = operation.apply(dataset)
        self.assertEqual(len(result.result.validation_issues), 2)

    def test_reports_values_outside_allowed_set(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("status"),),
            rows=({"status": "active"}, {"status": "blocked"}, {"status": "draft"}),
        )
        operation = AllowedValuesValidationOperation(
            config=AllowedValuesValidationConfig(
                columns=(ColumnName("status"),),
                allowed_values=("active", "blocked"),
            )
        )
        result = operation.apply(dataset)
        self.assertEqual(len(result.result.validation_issues), 1)
        self.assertEqual(result.result.validation_issues[0].value, "draft")

    def test_reports_invalid_email_and_date_values(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("email"), ColumnName("signup_date")),
            rows=(
                {"email": "alice@example.com", "signup_date": "2026-01-02"},
                {"email": "bad", "signup_date": "broken"},
            ),
        )
        email_result = EmailValidationOperation(
            config=EmailValidationConfig(columns=(ColumnName("email"),))
        ).apply(dataset)
        date_result = DateParseabilityValidationOperation(
            config=DateParseabilityValidationConfig(
                columns=(ColumnName("signup_date"),),
                formats=("%Y-%m-%d",),
            )
        ).apply(dataset)
        self.assertEqual(email_result.result.validation_issues[0].rule, "valid_email")
        self.assertEqual(date_result.result.validation_issues[0].rule, "parseable_date")


if __name__ == "__main__":
    unittest.main()
