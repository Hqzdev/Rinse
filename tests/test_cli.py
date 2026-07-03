import tempfile
import unittest
import json
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

    def test_clean_writes_report_and_runs_required_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dirty.csv"
            target = Path(directory) / "clean.json"
            report = Path(directory) / "report.json"
            source.write_text("name,email\nAlice,alice@example.com\nBob,\n")
            result = CliRunner().invoke(
                app,
                [
                    "clean",
                    str(source),
                    "--out",
                    str(target),
                    "--report",
                    str(report),
                    "--validate",
                    "required",
                    "--required-columns",
                    "name,email",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(target.exists())
            self.assertTrue(report.exists())
            self.assertIn(f"report: {report}", result.output)
            content = json.loads(report.read_text())
            self.assertEqual(content["validation_issue_count"], 1)
            self.assertEqual(content["operations"][0]["issues"][0]["column"], "email")
            self.assertEqual(content["export_artifacts"][0]["location"], "clean.json")

    def test_clean_writes_html_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dirty.csv"
            target = Path(directory) / "clean.json"
            report = Path(directory) / "report.html"
            source.write_text("name,email\nAlice,alice@example.com\nBob,\n")
            result = CliRunner().invoke(
                app,
                [
                    "clean",
                    str(source),
                    "--out",
                    str(target),
                    "--report",
                    str(report),
                    "--validate",
                    "required",
                    "--required-columns",
                    "name,email",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(report.exists())
            content = report.read_text()
            self.assertIn("<title>Rinse Cleaning Report</title>", content)
            self.assertIn("Validation issues", content)
            self.assertIn("Export artifacts", content)
            self.assertIn("clean.json", content)
            self.assertIn("email", content)

    def test_clean_writes_report_for_conversion_without_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dirty.csv"
            target = Path(directory) / "clean.json"
            report = Path(directory) / "report.json"
            source.write_text("name,email\nAlice,alice@example.com\n")
            result = CliRunner().invoke(
                app,
                ["clean", str(source), "--out", str(target), "--report", str(report)],
            )
            self.assertEqual(result.exit_code, 0)
            content = json.loads(report.read_text())
            self.assertEqual(content["rows_before"], 1)
            self.assertEqual(content["rows_after"], 1)
            self.assertEqual(content["operations"], [])

    def test_clean_supports_type_inference_missing_values_and_validation_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dirty.csv"
            target = Path(directory) / "clean.json"
            report = Path(directory) / "report.json"
            source.write_text(
                "name,email,signup_date,amount,status\n"
                "Alice,alice@example.com,2026-01-02,10,active\n"
                "Bob,bad,broken,,draft\n"
                "Carla,carla@example.com,2026-02-03,-5,blocked\n"
            )
            result = CliRunner().invoke(
                app,
                [
                    "clean",
                    str(source),
                    "--out",
                    str(target),
                    "--report",
                    str(report),
                    "--infer-types",
                    "--type-columns",
                    "amount,signup_date",
                    "--missing-policy",
                    "fill",
                    "--missing-columns",
                    "amount",
                    "--fill-value",
                    "1",
                    "--validate",
                    "email,date,positive,allowed",
                    "--valid-email-columns",
                    "email",
                    "--parseable-date-columns",
                    "signup_date",
                    "--positive-columns",
                    "amount",
                    "--allowed-columns",
                    "status",
                    "--allowed-values",
                    "active,blocked",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            content = json.loads(report.read_text())
            self.assertEqual(content["cells_changed"], 1)
            self.assertEqual(content["validation_issue_count"], 4)
            self.assertEqual(content["operations"][0]["type_suggestions"][0]["column"], "amount")
            self.assertEqual(content["operations"][1]["cell_changes"][0]["after"], "1")

    def test_clean_returns_nonzero_for_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "clean.csv"
            result = CliRunner().invoke(app, ["clean", "missing.csv", "--out", str(target)])
            self.assertNotEqual(result.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
