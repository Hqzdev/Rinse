from dataclasses import dataclass

from rinse.domain.value_objects import DatasetReference
from rinse.ports.datasets import DatasetReader


@dataclass(frozen=True)
class ProfileDatasetRequest:
    source: DatasetReference


@dataclass(frozen=True)
class ProfileDatasetResult:
    rows: int
    columns: int
    column_names: tuple[str, ...]


@dataclass(frozen=True)
class ProfileDataset:
    reader: DatasetReader

    def execute(self, request: ProfileDatasetRequest) -> ProfileDatasetResult:
        dataset = self.reader.read(request.source)
        return ProfileDatasetResult(
            rows=dataset.row_count,
            columns=dataset.column_count,
            column_names=tuple(column.value for column in dataset.columns),
        )
