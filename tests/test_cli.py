import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from rinse.interfaces.cli import app


class CliTests(unittest.TestCase):
    def test_profile_prints_dataset_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dirty.csv"
            source.write_text("name,email\nAlice,alice@example.com\nBob,bob@example.com\n")
            result = CliRunner().invoke(app, ["profile", str(source)])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("rows: 2", result.output)
            self.assertIn("columns: 2", result.output)
            self.assertIn("column_names: name, email", result.output)

    def test_clean_writes_output_and_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dirty.csv"
            target = Path(directory) / "clean.csv"
            source.write_text("name,email\n Alice ,ALICE@EXAMPLE.COM\nalice,alice@example.com\n")
            result = CliRunner().invoke(
                app,
                [
                    "clean",
                    str(source),
                    "--out",
                    str(target),
                    "--normalize",
                    "text,email",
                    "--text-columns",
                    "name",
                    "--email-columns",
                    "email",
                    "--text-case",
                    "lower",
                    "--dedup",
                    "exact",
                    "--dedup-columns",
                    "name,email",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(target.exists())
            self.assertIn("rows_before: 2", result.output)
            self.assertIn("rows_after: 1", result.output)
            self.assertIn("rows_removed: 1", result.output)
            self.assertIn("cells_changed: 2", result.output)
            self.assertIn("validation_issues: 0", result.output)

    def test_clean_returns_nonzero_for_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "clean.csv"
            result = CliRunner().invoke(app, ["clean", "missing.csv", "--out", str(target)])
            self.assertNotEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
