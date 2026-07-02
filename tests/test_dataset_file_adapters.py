import json
import tempfile
import unittest
from pathlib import Path

from rinse.adapters import (
    DatasetFileError,
    PandasDatasetReader,
    PandasDatasetWriter,
    UnsupportedDatasetFormatError,
)
from rinse.adapters.dataset_files import DatasetFormatDetector
from rinse.domain import ColumnName, Dataset, DatasetFormat, DatasetReference


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


if __name__ == "__main__":
    unittest.main()
