import unittest

from rinse.adapters import PhoneNumbersNormalizer
from rinse.domain import (
    ColumnName,
    Dataset,
    DateNormalizationConfig,
    DateNormalizationOperation,
    EmailNormalizationConfig,
    EmailNormalizationOperation,
    PhoneNormalizationConfig,
    PhoneNormalizationOperation,
    TextCase,
    TextNormalizationConfig,
    TextNormalizationOperation,
)


def messy_dataset() -> Dataset:
    return Dataset(
        columns=(ColumnName("name"), ColumnName("email"), ColumnName("signup_date"), ColumnName("phone")),
        rows=(
            {
                "name": "  alice   smith ",
                "email": " ALICE@EXAMPLE.COM ",
                "signup_date": "01/02/2026",
                "phone": "(415) 555-2671",
            },
            {
                "name": "BOB",
                "email": "not-an-email",
                "signup_date": "broken",
                "phone": "123",
            },
        ),
    )


class NormalizationOperationTests(unittest.TestCase):
    def test_normalizes_text_and_reports_changes(self) -> None:
        operation = TextNormalizationOperation(
            config=TextNormalizationConfig(columns=(ColumnName("name"),), case=TextCase.TITLE)
        )
        result = operation.apply(messy_dataset())
        self.assertEqual(result.dataset.rows[0]["name"], "Alice Smith")
        self.assertEqual(result.dataset.rows[1]["name"], "Bob")
        self.assertEqual(len(result.result.cells_changed), 2)
        self.assertEqual(result.result.validation_issues, ())

    def test_normalizes_email_and_reports_invalid_values(self) -> None:
        operation = EmailNormalizationOperation(
            config=EmailNormalizationConfig(columns=(ColumnName("email"),))
        )
        result = operation.apply(messy_dataset())
        self.assertEqual(result.dataset.rows[0]["email"], "alice@example.com")
        self.assertEqual(result.dataset.rows[1]["email"], "not-an-email")
        self.assertEqual(len(result.result.cells_changed), 1)
        self.assertEqual(len(result.result.validation_issues), 1)
        self.assertEqual(result.result.validation_issues[0].rule, "valid_email")

    def test_normalizes_dates_and_reports_parse_failures(self) -> None:
        operation = DateNormalizationOperation(
            config=DateNormalizationConfig(
                columns=(ColumnName("signup_date"),),
                input_formats=("%m/%d/%Y", "%Y-%m-%d"),
                output_format="%Y-%m-%d",
            )
        )
        result = operation.apply(messy_dataset())
        self.assertEqual(result.dataset.rows[0]["signup_date"], "2026-01-02")
        self.assertEqual(result.dataset.rows[1]["signup_date"], "broken")
        self.assertEqual(len(result.result.cells_changed), 1)
        self.assertEqual(len(result.result.validation_issues), 1)
        self.assertEqual(result.result.validation_issues[0].rule, "parseable_date")

    def test_normalizes_phones_and_reports_invalid_values(self) -> None:
        operation = PhoneNormalizationOperation(
            config=PhoneNormalizationConfig(columns=(ColumnName("phone"),), default_region="US"),
            normalizer=PhoneNumbersNormalizer(),
        )
        result = operation.apply(messy_dataset())
        self.assertEqual(result.dataset.rows[0]["phone"], "+14155552671")
        self.assertEqual(result.dataset.rows[1]["phone"], "123")
        self.assertEqual(len(result.result.cells_changed), 1)
        self.assertEqual(len(result.result.validation_issues), 1)
        self.assertEqual(result.result.validation_issues[0].rule, "valid_phone")

    def test_phone_normalization_requires_region(self) -> None:
        with self.assertRaises(ValueError):
            PhoneNormalizationConfig(columns=(ColumnName("phone"),), default_region="")


if __name__ == "__main__":
    unittest.main()
