from dataclasses import dataclass
from typing import Protocol

from rinse.domain.entities import Dataset, OperationResult


@dataclass(frozen=True)
class OperationOutcome:
    dataset: Dataset
    result: OperationResult


class CleaningOperation(Protocol):
    @property
    def name(self) -> str:
        raise NotImplementedError

    def apply(self, dataset: Dataset) -> OperationOutcome:
        raise NotImplementedError
