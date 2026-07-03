import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from rinse.interfaces.cli import app


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class RealisticGoldenCleaningTests(unittest.TestCase):
    def test_realistic_csv_matches_golden_output_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "clean.json"
            report = Path(directory) / "report.json"
            result = run_realistic_clean(FIXTURES / "dirty_realistic_customers.csv", target, report)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(
                json.loads(target.read_text()),
                load_fixture("expected_realistic_customers_clean.json"),
            )
            self.assertEqual(
                json.loads(report.read_text()),
                load_fixture("expected_realistic_customers_report.json"),
            )

    def test_realistic_xlsx_matches_golden_output_and_report_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "clean.json"
            report = Path(directory) / "report.json"
            result = run_realistic_clean(FIXTURES / "dirty_realistic_customers.xlsx", target, report)
            self.assertEqual(result.exit_code, 0)
            content = json.loads(report.read_text())
            self.assertEqual(
                json.loads(target.read_text()),
                load_fixture("expected_realistic_customers_clean.json"),
            )
            self.assertEqual(content["rows_before"], 5)
            self.assertEqual(content["rows_after"], 4)
            self.assertEqual(content["rows_removed"], 1)
            self.assertEqual(content["cells_changed"], 9)
            self.assertEqual(content["validation_issue_count"], 8)
            self.assertEqual(content["duplicate_group_count"], 1)


def run_realistic_clean(source: Path, target: Path, report: Path):
    return CliRunner().invoke(
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
            "--normalize",
            "text,email,date,phone",
            "--text-columns",
            "name,status",
            "--email-columns",
            "email",
            "--date-columns",
            "signup_date",
            "--date-input-format",
            "%m/%d/%Y,%Y-%m-%d",
            "--phone-columns",
            "phone",
            "--validate",
            "required,email,date,positive,allowed",
            "--required-columns",
            "customer_id,name,email,signup_date,amount",
            "--valid-email-columns",
            "email",
            "--parseable-date-columns",
            "signup_date",
            "--validation-date-format",
            "%Y-%m-%d,%m/%d/%Y",
            "--positive-columns",
            "amount",
            "--allowed-columns",
            "status",
            "--allowed-values",
            "active,blocked",
            "--dedup",
            "fuzzy",
            "--dedup-columns",
            "name,email",
            "--fuzzy-threshold",
            "96",
            "--fuzzy-mode",
            "remove_strict",
        ],
    )


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


if __name__ == "__main__":
    unittest.main()
