from typing import Protocol

from rinse.domain.entities import CleaningReport
from rinse.domain.value_objects import DatasetReference


class ReportWriter(Protocol):
    def write(self, report: CleaningReport, target: DatasetReference) -> DatasetReference:
        raise NotImplementedError
