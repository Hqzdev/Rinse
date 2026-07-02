from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

CellValue = Union[str, int, float, bool, None]


class DatasetFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"
    JSON = "json"


@dataclass(frozen=True)
class ColumnName:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("Column name cannot be empty")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class RowIndex:
    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Row index cannot be negative")


@dataclass(frozen=True)
class DatasetReference:
    location: str
    format: Optional[DatasetFormat] = None

    def __post_init__(self) -> None:
        normalized = self.location.strip()
        if not normalized:
            raise ValueError("Dataset reference location cannot be empty")
        object.__setattr__(self, "location", normalized)


@dataclass(frozen=True)
class CellChange:
    row: RowIndex
    column: ColumnName
    before: CellValue
    after: CellValue
    reason: str

    def __post_init__(self) -> None:
        normalized = self.reason.strip()
        if not normalized:
            raise ValueError("Cell change reason cannot be empty")
        object.__setattr__(self, "reason", normalized)
