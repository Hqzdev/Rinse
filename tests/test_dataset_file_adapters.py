import json
import tempfile
import unittest
from pathlib import Path

from rinse.adapters import (
    DatasetFileError,
    HtmlReportWriter,
    JsonReportWriter,
    PandasDatasetReader,
    PandasDatasetWriter,
    UnsupportedDatasetFormatError,
)
from rinse.adapters.dataset_files import DatasetFormatDetector
from rinse.domain import (
    CellChange,
    CleaningReport,
    ColumnName,
    ColumnTypeSuggestion,
    Dataset,
    DatasetFormat,
    DatasetReference,
    DuplicateGroup,
    ExportArtifact,
    OperationResult,
    RowIndex,
    ValidationIssue,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class DatasetFileAdapterTests(unittest.TestCase):
    def test_detects_format_from_extension(self) -> None:
        detector = DatasetFormatDetector()
        self.assertEqual(detector.detect(DatasetReference("sample.csv")), DatasetFormat.CSV)
        self.assertEqual(detector.detect(DatasetReference("sample.xlsx")), DatasetFormat.XLSX)
        self.assertEqual(detector.detect(DatasetReference("sample.json")), DatasetFormat.JSON)

    def test_rejects_unsupported_extension(self) -> None:
        detector = DatasetFormatDetector()
        with self.assertRaises(UnsupportedDatasetFormatError):
            detector.detect(DatasetReference("sample.txt"))

    def test_rejects_missing_file(self) -> None:
        reader = PandasDatasetReader()
        with self.assertRaises(DatasetFileError):
            reader.read(DatasetReference("missing.csv"))

    def test_exports_csv_fixture_to_expected_json_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "clean.json"
            reader = PandasDatasetReader()
            writer = PandasDatasetWriter()
            dataset = reader.read(DatasetReference(str(FIXTURES / "dirty_customers.csv")))
            writer.write(dataset, DatasetReference(str(target)))
            self.assertEqual(
                json.loads(target.read_text()),
                json.loads((FIXTURES / "expected_customers.json").read_text()),
            )

    def test_round_trips_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dirty.csv"
            target = Path(directory) / "clean.csv"
            source.write_text("name,email\nAlice,alice@example.com\nBob,\n")
            reader = PandasDatasetReader()
            writer = PandasDatasetWriter()
            dataset = reader.read(DatasetReference(str(source)))
            writer.write(dataset, DatasetReference(str(target)))
            round_tripped = reader.read(DatasetReference(str(target)))
            self.assertEqual(round_tripped.row_count, 2)
            self.assertEqual(tuple(column.value for column in round_tripped.columns), ("name", "email"))
            self.assertEqual(round_tripped.rows[1]["email"], None)

    def test_writes_json_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "clean.json"
            dataset = Dataset(
                columns=(ColumnName("name"), ColumnName("email")),
                rows=(
                    {"name": "Alice", "email": "alice@example.com"},
                    {"name": "Bob", "email": None},
                ),
            )
            writer = PandasDatasetWriter()
            writer.write(dataset, DatasetReference(str(target)))
            self.assertEqual(
                json.loads(target.read_text()),
                [
                    {"name": "Alice", "email": "alice@example.com"},
                    {"name": "Bob", "email": None},
                ],
            )

    def test_round_trips_xlsx_first_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "clean.xlsx"
            dataset = Dataset(
                columns=(ColumnName("name"), ColumnName("email")),
                rows=(
                    {"name": "Alice", "email": "alice@example.com"},
                    {"name": "Bob", "email": None},
                ),
            )
            reader = PandasDatasetReader()
            writer = PandasDatasetWriter()
            writer.write(dataset, DatasetReference(str(target)))
            round_tripped = reader.read(DatasetReference(str(target)))
            self.assertEqual(round_tripped.row_count, 2)
            self.assertEqual(tuple(column.value for column in round_tripped.columns), ("name", "email"))
            self.assertEqual(round_tripped.rows[1]["email"], None)

    def test_writes_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            report = CleaningReport(
                rows_before=1,
                rows_after=1,
                operation_results=(
                    OperationResult(
                        name="text-normalization",
                        cells_changed=(
                            CellChange(
                                row=RowIndex(0),
                                column=ColumnName("name"),
                                before=" Alice ",
                                after="Alice",
                                reason="text-normalization",
                            ),
                        ),
                    ),
                ),
            )
            JsonReportWriter().write(report, DatasetReference(str(target)))
            content = json.loads(target.read_text())
            self.assertEqual(content["cells_changed"], 1)
            self.assertEqual(content["operations"][0]["cell_changes"][0]["after"], "Alice")

    def test_writes_html_report_from_structured_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.html"
            report = CleaningReport(
                rows_before=3,
                rows_after=2,
                operation_results=(
                    OperationResult(
                        name="quality-check",
                        rows_removed=1,
                        cells_changed=(
                            CellChange(
                                row=RowIndex(0),
                                column=ColumnName("name"),
                                before="< Alice ",
                                after="Alice",
                                reason="text-normalization",
                            ),
                        ),
                        validation_issues=(
                            ValidationIssue(
                                row=RowIndex(1),
                                column=ColumnName("email"),
                                rule="email",
                                value="bad-email",
                                message="Invalid email",
                            ),
                        ),
                        duplicate_groups=(
                            DuplicateGroup(
                                kept_row=RowIndex(0),
                                matched_rows=(RowIndex(2),),
                                score=96.5,
                                reason="fuzzy-match",
                            ),
                        ),
                        type_suggestions=(
                            ColumnTypeSuggestion(
                                column=ColumnName("amount"),
                                suggested_type="number",
                                confidence=0.92,
                                reason="numeric values",
                            ),
                        ),
                    ),
                ),
                export_artifacts=(
                    ExportArtifact(label="Clean output", location="clean.json", kind="json"),
                    ExportArtifact(label="Audit report", location="report.html", kind="html"),
                ),
            )
            HtmlReportWriter().write(report, DatasetReference(str(target)))
            content = target.read_text()
            self.assertIn("<title>Rinse Cleaning Report</title>", content)
            self.assertIn("Summary", content)
            self.assertIn("Cell changes", content)
            self.assertIn("Validation issues", content)
            self.assertIn("Duplicate groups", content)
            self.assertIn("Type suggestions", content)
            self.assertIn("Export artifacts", content)
            self.assertIn("clean.json", content)
            self.assertIn("&lt; Alice ", content)
            self.assertIn("96.5", content)


if __name__ == "__main__":
    unittest.main()
