from html import escape
from pathlib import Path
from typing import Any, Mapping

from rinse.domain.entities import CleaningReport
from rinse.domain.value_objects import DatasetReference


class HtmlReportWriter:
    def write(self, report: CleaningReport, target: DatasetReference) -> DatasetReference:
        path = Path(target.location)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(report), encoding="utf-8")
        return target

    def render(self, report: CleaningReport) -> str:
        content = report.to_dict()
        operations = tuple(content["operations"])
        return "\n".join(
            (
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                "<title>Rinse Cleaning Report</title>",
                f"<style>{self.styles()}</style>",
                "</head>",
                "<body>",
                '<main class="report">',
                self.header(content),
                self.summary(content),
                self.operations(operations),
                self.cell_changes(operations),
                self.validation_issues(operations),
                self.duplicate_groups(operations),
                self.type_suggestions(operations),
                self.export_artifacts(tuple(content["export_artifacts"])),
                "</main>",
                "</body>",
                "</html>",
            )
        )

    def header(self, content: Mapping[str, Any]) -> str:
        return "\n".join(
            (
                '<section class="hero">',
                "<span>Rinse audit report</span>",
                "<h1>Cleaning run summary</h1>",
                f"<p>{self.text(content['rows_before'])} input rows became {self.text(content['rows_after'])} output rows through a structured cleaning pipeline.</p>",
                "</section>",
            )
        )

    def summary(self, content: Mapping[str, Any]) -> str:
        metrics = (
            ("Rows before", content["rows_before"]),
            ("Rows after", content["rows_after"]),
            ("Rows removed", content["rows_removed"]),
            ("Cells changed", content["cells_changed"]),
            ("Validation issues", content["validation_issue_count"]),
            ("Duplicate groups", content["duplicate_group_count"]),
        )
        return self.section(
            "Summary",
            '<div class="metrics">'
            + "".join(
                f'<article><span>{self.text(label)}</span><b>{self.text(value)}</b></article>'
                for label, value in metrics
            )
            + "</div>",
        )

    def operations(self, operations: tuple[Any, ...]) -> str:
        rows = [
            (
                operation["name"],
                operation["rows_removed"],
                operation["cells_changed"],
                operation["validation_issues"],
                operation["duplicate_groups"],
            )
            for operation in operations
        ]
        return self.table_section(
            "Operations",
            ("Operation", "Rows removed", "Cells changed", "Issues", "Duplicate groups"),
            rows,
            "No operations were applied.",
        )

    def cell_changes(self, operations: tuple[Any, ...]) -> str:
        rows = [
            (
                operation["name"],
                change["row"],
                change["column"],
                change["before"],
                change["after"],
                change["reason"],
            )
            for operation in operations
            for change in operation["cell_changes"]
        ]
        return self.table_section(
            "Cell changes",
            ("Operation", "Row", "Column", "Before", "After", "Reason"),
            rows,
            "No cell changes were recorded.",
        )

    def validation_issues(self, operations: tuple[Any, ...]) -> str:
        rows = [
            (
                operation["name"],
                issue["row"],
                issue["column"],
                issue["rule"],
                issue["value"],
                issue["message"],
            )
            for operation in operations
            for issue in operation["issues"]
        ]
        return self.table_section(
            "Validation issues",
            ("Operation", "Row", "Column", "Rule", "Value", "Message"),
            rows,
            "No validation issues were recorded.",
        )

    def duplicate_groups(self, operations: tuple[Any, ...]) -> str:
        rows = [
            (
                operation["name"],
                duplicate["kept_row"],
                ", ".join(str(row) for row in duplicate["matched_rows"]),
                duplicate["score"],
                duplicate["reason"],
            )
            for operation in operations
            for duplicate in operation["duplicates"]
        ]
        return self.table_section(
            "Duplicate groups",
            ("Operation", "Kept row", "Matched rows", "Score", "Reason"),
            rows,
            "No duplicate groups were recorded.",
        )

    def type_suggestions(self, operations: tuple[Any, ...]) -> str:
        rows = [
            (
                operation["name"],
                suggestion["column"],
                suggestion["suggested_type"],
                f"{float(suggestion['confidence']) * 100:.0f}%",
                suggestion["reason"],
            )
            for operation in operations
            for suggestion in operation["type_suggestions"]
        ]
        return self.table_section(
            "Type suggestions",
            ("Operation", "Column", "Suggested type", "Confidence", "Reason"),
            rows,
            "No type suggestions were recorded.",
        )

    def export_artifacts(self, artifacts: tuple[Any, ...]) -> str:
        rows = [
            (
                artifact["label"],
                artifact["kind"],
                artifact["location"],
            )
            for artifact in artifacts
        ]
        return self.table_section(
            "Export artifacts",
            ("Label", "Kind", "Location"),
            rows,
            "No export artifacts were recorded.",
        )

    def table_section(
        self,
        title: str,
        headers: tuple[str, ...],
        rows: list[tuple[Any, ...]],
        empty: str,
    ) -> str:
        if not rows:
            return self.section(title, f'<p class="empty">{self.text(empty)}</p>')
        head = "".join(f"<th>{self.text(header)}</th>" for header in headers)
        body = "".join(
            "<tr>" + "".join(f"<td>{self.text(value)}</td>" for value in row) + "</tr>"
            for row in rows
        )
        return self.section(title, f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")

    def section(self, title: str, body: str) -> str:
        return "\n".join(('<section class="block">', f"<h2>{self.text(title)}</h2>", body, "</section>"))

    def text(self, value: Any) -> str:
        if value is None:
            return '<span class="muted">NULL</span>'
        return escape(str(value), quote=True)

    def styles(self) -> str:
        return """
:root{color-scheme:light dark;font-family:Avenir Next,Segoe UI,system-ui,sans-serif;background:#f7f5ef;color:#202329}
body{margin:0;background:#f7f5ef;color:#202329}
.report{width:min(1120px,calc(100% - 40px));margin:0 auto;padding:56px 0 72px}
.hero{border-bottom:1px solid #d9d4c7;padding-bottom:28px}
.hero span{color:#0f766e;font-family:SFMono-Regular,Consolas,monospace;font-size:12px;letter-spacing:.12em;text-transform:uppercase}
h1{margin:10px 0 0;font-size:52px;line-height:1;font-weight:580;letter-spacing:-.026em}
h2{margin:0 0 16px;font-size:22px;font-weight:620}
p{max-width:720px;color:#5f6670;line-height:1.65}
.block{margin-top:34px;border:1px solid #d9d4c7;background:#fff;padding:20px;box-shadow:0 16px 48px rgb(35 38 42 / 8%)}
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#d9d4c7;border:1px solid #d9d4c7}
.metrics article{background:#fff;padding:16px}
.metrics span{display:block;color:#68707c;font-size:13px}
.metrics b{display:block;margin-top:8px;font-family:SFMono-Regular,Consolas,monospace;font-size:24px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{border-top:1px solid #e7e2d7;padding:10px;text-align:left;vertical-align:top}
th{color:#68707c;font-family:SFMono-Regular,Consolas,monospace;font-size:11px;text-transform:uppercase}
td{font-family:SFMono-Regular,Consolas,monospace}
.empty,.muted{color:#68707c}
@media (prefers-color-scheme:dark){:root,body{background:#191b1f;color:#e7e9ec}.hero{border-color:#333841}p,.empty,.muted{color:#9aa2af}.block,.metrics article{background:#202329}.block,.metrics,th,td{border-color:#333841}.metrics{background:#333841}.hero span{color:#66b8ad}th{color:#9aa2af}}
@media (max-width:760px){.report{width:min(100% - 28px,1120px);padding-top:34px}h1{font-size:40px}.metrics{grid-template-columns:1fr}.block{overflow-x:auto}}
""".strip()
