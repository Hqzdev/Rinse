import json
from pathlib import Path

from rinse.domain.entities import CleaningReport
from rinse.domain.value_objects import DatasetReference


class JsonReportWriter:
    def write(self, report: CleaningReport, target: DatasetReference) -> DatasetReference:
        path = Path(target.location)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return target
