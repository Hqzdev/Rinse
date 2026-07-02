from dataclasses import dataclass
from typing import Protocol

from rinse.domain.value_objects import DatasetReference


@dataclass(frozen=True)
class StoredArtifact:
    id: str
    reference: DatasetReference

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Stored artifact id cannot be empty")


class FileStorage(Protocol):
    def save(self, source: DatasetReference) -> StoredArtifact:
        raise NotImplementedError

    def load(self, artifact_id: str) -> DatasetReference:
        raise NotImplementedError
