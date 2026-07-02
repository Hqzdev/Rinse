from typing import Protocol

from rinse.domain.entities import Dataset
from rinse.domain.value_objects import DatasetReference


class DatasetReader(Protocol):
    def read(self, source: DatasetReference) -> Dataset:
        raise NotImplementedError


class DatasetWriter(Protocol):
    def write(self, dataset: Dataset, target: DatasetReference) -> DatasetReference:
        raise NotImplementedError
