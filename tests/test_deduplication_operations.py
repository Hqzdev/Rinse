import unittest

from rinse.adapters import RapidFuzzTextSimilarity
from rinse.domain import (
    ColumnName,
    DeduplicationConfig,
    DeduplicationMode,
    Dataset,
    ExactDeduplicationOperation,
    FuzzyDeduplicationConfig,
    FuzzyDeduplicationOperation,
)


def customer_dataset() -> Dataset:
    return Dataset(
        columns=(ColumnName("name"), ColumnName("email"), ColumnName("city")),
        rows=(
            {"name": " Alice Smith ", "email": "alice@example.com", "city": "London"},
            {"name": "alice smith", "email": "alice@example.com", "city": "London"},
            {"name": "Bob Stone", "email": "bob@example.com", "city": "Paris"},
            {"name": "Bob Stone", "email": "other@example.com", "city": "Paris"},
        ),
    )


def russian_names_dataset() -> Dataset:
    return Dataset(
        columns=(ColumnName("name"), ColumnName("email")),
        rows=(
            {"name": "Иван Петров", "email": "ivan@example.com"},
            {"name": "Петров Иван", "email": "ivan.duplicate@example.com"},
            {"name": "Иван Петрович", "email": "other@example.com"},
        ),
    )


def risky_names_dataset() -> Dataset:
    return Dataset(
        columns=(ColumnName("name"), ColumnName("email")),
        rows=(
            {"name": "Иван Петров", "email": "ivan@example.com"},
            {"name": "Иван Сидоров", "email": "sidorov@example.com"},
        ),
    )


class DeduplicationOperationTests(unittest.TestCase):
    def test_exact_dedup_removes_full_row_duplicates_after_normalization(self) -> None:
        dataset = Dataset(
            columns=(ColumnName("name"), ColumnName("email")),
            rows=(
                {"name": " Alice Smith ", "email": "alice@example.com"},
                {"name": "alice   smith", "email": "alice@example.com"},
                {"name": "Bob Stone", "email": "bob@example.com"},
            ),
        )
        result = ExactDeduplicationOperation().apply(dataset)
        self.assertEqual(result.dataset.row_count, 2)
        self.assertEqual(result.result.rows_removed, 1)
        self.assertEqual(result.result.duplicate_groups[0].kept_row.value, 0)
        self.assertEqual(result.result.duplicate_groups[0].matched_rows[0].value, 1)
        self.assertEqual(result.result.duplicate_groups[0].score, 100)

    def test_exact_dedup_removes_duplicates_by_selected_columns(self) -> None:
        result = ExactDeduplicationOperation(
            config=DeduplicationConfig(columns=(ColumnName("name"), ColumnName("city")))
        ).apply(customer_dataset())
        self.assertEqual(result.dataset.row_count, 2)
        self.assertEqual(result.result.rows_removed, 2)
        self.assertEqual(len(result.result.duplicate_groups), 2)

    def test_fuzzy_dedup_suggests_name_order_variants_without_removing_rows(self) -> None:
        operation = FuzzyDeduplicationOperation(
            config=FuzzyDeduplicationConfig(
                columns=(ColumnName("name"),),
                threshold=92,
                mode=DeduplicationMode.SUGGEST,
            ),
            similarity=RapidFuzzTextSimilarity(),
        )
        result = operation.apply(russian_names_dataset())
        self.assertEqual(result.dataset.row_count, 3)
        self.assertEqual(result.result.rows_removed, 0)
        self.assertEqual(len(result.result.duplicate_groups), 1)
        self.assertEqual(result.result.duplicate_groups[0].kept_row.value, 0)
        self.assertEqual(result.result.duplicate_groups[0].matched_rows[0].value, 1)
        self.assertGreaterEqual(result.result.duplicate_groups[0].score, 92)

    def test_fuzzy_dedup_remove_strict_removes_only_above_threshold(self) -> None:
        operation = FuzzyDeduplicationOperation(
            config=FuzzyDeduplicationConfig(
                columns=(ColumnName("name"),),
                threshold=92,
                mode=DeduplicationMode.REMOVE_STRICT,
            ),
            similarity=RapidFuzzTextSimilarity(),
        )
        result = operation.apply(russian_names_dataset())
        self.assertEqual(result.dataset.row_count, 2)
        self.assertEqual(result.result.rows_removed, 1)
        self.assertEqual([row["name"] for row in result.dataset.rows], ["Иван Петров", "Иван Петрович"])

    def test_fuzzy_dedup_does_not_remove_false_positive_below_threshold(self) -> None:
        operation = FuzzyDeduplicationOperation(
            config=FuzzyDeduplicationConfig(
                columns=(ColumnName("name"),),
                threshold=98,
                mode=DeduplicationMode.REMOVE_STRICT,
            ),
            similarity=RapidFuzzTextSimilarity(),
        )
        result = operation.apply(risky_names_dataset())
        self.assertEqual(result.dataset.row_count, 2)
        self.assertEqual(result.result.rows_removed, 0)
        self.assertEqual(len(result.result.duplicate_groups), 0)

    def test_fuzzy_dedup_rejects_missing_columns_and_invalid_threshold(self) -> None:
        with self.assertRaises(ValueError):
            FuzzyDeduplicationConfig(columns=(), threshold=90)
        with self.assertRaises(ValueError):
            FuzzyDeduplicationConfig(columns=(ColumnName("name"),), threshold=101)


if __name__ == "__main__":
    unittest.main()
