from dataclasses import dataclass

from rinse.domain.entities import CleaningReport, Dataset, OperationResult
from rinse.domain.operations import CleaningOperation


@dataclass(frozen=True)
class CleaningPipelineRequest:
    dataset: Dataset
    preview: bool = False


@dataclass(frozen=True)
class CleaningPipelineResult:
    dataset: Dataset
    report: CleaningReport
    preview: bool


@dataclass(frozen=True)
class CleaningPipeline:
    operations: tuple[CleaningOperation, ...]

    def __post_init__(self) -> None:
        if not self.operations:
            raise ValueError("Cleaning pipeline requires at least one operation")
        names = [operation.name.strip() for operation in self.operations]
        if any(not name for name in names):
            raise ValueError("Cleaning operation name cannot be empty")
        if len(names) != len(set(names)):
            raise ValueError("Cleaning operation names must be unique")

    def run(self, request: CleaningPipelineRequest) -> CleaningPipelineResult:
        current = request.dataset
        results: list[OperationResult] = []
        rows_before = current.row_count
        for operation in self.operations:
            outcome = operation.apply(current)
            current = outcome.dataset
            results.append(outcome.result)
        report = CleaningReport(
            rows_before=rows_before,
            rows_after=current.row_count,
            operation_results=tuple(results),
        )
        return CleaningPipelineResult(dataset=current, report=report, preview=request.preview)
