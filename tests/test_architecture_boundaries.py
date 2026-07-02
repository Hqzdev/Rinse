import ast
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "rinse"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                modules.update(".".join(parts[:index]) for index in range(1, len(parts) + 1))
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            modules.update(".".join(parts[:index]) for index in range(1, len(parts) + 1))
    return modules


def python_files(package: str) -> list[Path]:
    return sorted((SOURCE_ROOT / package).rglob("*.py"))


class ArchitectureBoundaryTests(unittest.TestCase):
    def assert_no_imports(self, package: str, banned: set[str]) -> None:
        violations = {
            path.relative_to(SOURCE_ROOT): imported_modules(path) & banned
            for path in python_files(package)
            if imported_modules(path) & banned
        }
        self.assertEqual(violations, {})

    def test_domain_has_no_external_interface_or_infrastructure_imports(self) -> None:
        self.assert_no_imports(
            "domain",
            {
                "fastapi",
                "openpyxl",
                "pandas",
                "phonenumbers",
                "rapidfuzz",
                "redis",
                "sqlalchemy",
                "typer",
            },
        )

    def test_application_does_not_import_concrete_adapters_or_interfaces(self) -> None:
        self.assert_no_imports(
            "application",
            {"phonenumbers", "rapidfuzz", "rinse.adapters", "rinse.infrastructure", "rinse.interfaces"},
        )


if __name__ == "__main__":
    unittest.main()
