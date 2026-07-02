from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from rinse.domain.entities import Dataset, DuplicateGroup, OperationResult
from rinse.domain.operations import OperationOutcome
from rinse.domain.value_objects import CellValue, ColumnName, RowIndex


class DeduplicationMode(str, Enum):
    SUGGEST = "suggest"
    REMOVE_STRICT = "remove_strict"


class TextSimilarity(Protocol):
    def score(self, left: str, right: str) -> float:
        raise NotImplementedError


@dataclass(frozen=True)
class DeduplicationConfig:
    columns: tuple[ColumnName, ...] = ()


@dataclass(frozen=True)
class FuzzyDeduplicationConfig:
    columns: tuple[ColumnName, ...]
    threshold: float
    mode: DeduplicationMode = DeduplicationMode.SUGGEST

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("Fuzzy deduplication requires at least one column")
        if not 0 <= self.threshold <= 100:
            raise ValueError("Fuzzy deduplication threshold must be between 0 and 100")


@dataclass(frozen=True)
class ExactDeduplicationOperation:
    config: DeduplicationConfig = DeduplicationConfig()
    name: str = "exact-deduplication"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        seen: dict[tuple[CellValue, ...], int] = {}
        kept_rows: list[Mapping[str, CellValue]] = []
        matched_rows_by_kept: dict[int, list[RowIndex]] = {}
        for index, row in enumerate(dataset.rows):
            key = row_key(row, dataset.columns, self.config.columns)
            kept_index = seen.get(key)
            if kept_index is None:
                seen[key] = index
                kept_rows.append(row)
            else:
                matched_rows_by_kept.setdefault(kept_index, []).append(RowIndex(index))
        duplicate_groups = tuple(
            DuplicateGroup(
                kept_row=RowIndex(kept_index),
                matched_rows=tuple(matched_rows),
                score=100,
                reason="exact duplicate",
            )
            for kept_index, matched_rows in matched_rows_by_kept.items()
        )
        rows_removed = sum(len(group.matched_rows) for group in duplicate_groups)
        return OperationOutcome(
            dataset=dataset.with_rows(tuple(kept_rows)),
            result=OperationResult(
                name=self.name,
                rows_removed=rows_removed,
                duplicate_groups=duplicate_groups,
            ),
        )


@dataclass(frozen=True)
class FuzzyDeduplicationOperation:
    config: FuzzyDeduplicationConfig
    similarity: TextSimilarity
    name: str = "fuzzy-deduplication"

    def apply(self, dataset: Dataset) -> OperationOutcome:
        removed_indexes: set[int] = set()
        duplicate_groups: list[DuplicateGroup] = []
        for kept_index, kept_row in enumerate(dataset.rows):
            if kept_index in removed_indexes:
                continue
            matched_rows: list[RowIndex] = []
            scores: list[float] = []
            kept_text = comparable_text(kept_row, self.config.columns)
            for candidate_index in range(kept_index + 1, dataset.row_count):
                if candidate_index in removed_indexes:
                    continue
                candidate_row = dataset.rows[candidate_index]
                candidate_text = comparable_text(candidate_row, self.config.columns)
                score = self.similarity.score(kept_text, candidate_text)
                if score >= self.config.threshold:
                    matched_rows.append(RowIndex(candidate_index))
                    scores.append(score)
                    if self.config.mode == DeduplicationMode.REMOVE_STRICT:
                        removed_indexes.add(candidate_index)
            if matched_rows:
                duplicate_groups.append(
                    DuplicateGroup(
                        kept_row=RowIndex(kept_index),
                        matched_rows=tuple(matched_rows),
                        score=min(scores),
                        reason=f"fuzzy duplicate above threshold {self.config.threshold:g}",
                    )
                )
        rows = tuple(row for index, row in enumerate(dataset.rows) if index not in removed_indexes)
        return OperationOutcome(
            dataset=dataset.with_rows(rows),
            result=OperationResult(
                name=self.name,
                rows_removed=len(removed_indexes),
                duplicate_groups=tuple(duplicate_groups),
            ),
        )


def row_key(
    row: Mapping[str, CellValue],
    all_columns: tuple[ColumnName, ...],
    selected_columns: tuple[ColumnName, ...],
) -> tuple[CellValue, ...]:
    columns = selected_columns or all_columns
    return tuple(normalize_exact_value(row.get(column.value)) for column in columns)


def normalize_exact_value(value: CellValue) -> CellValue:
    if isinstance(value, str):
        return " ".join(value.strip().casefold().split())
    return value


def comparable_text(row: Mapping[str, CellValue], columns: tuple[ColumnName, ...]) -> str:
    return " ".join(
        " ".join(str(row.get(column.value) or "").casefold().split())
        for column in columns
    ).strip()
