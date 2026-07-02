from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class JobHandle:
    id: str
    state: JobState

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Job id cannot be empty")


class JobQueue(Protocol):
    def enqueue(self, name: str, payload: Mapping[str, object]) -> JobHandle:
        raise NotImplementedError

    def status(self, job_id: str) -> JobHandle:
        raise NotImplementedError
