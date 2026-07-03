import json
import sqlite3
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from rinse.adapters import HtmlReportWriter, JsonReportWriter, PandasDatasetReader, PandasDatasetWriter
from rinse.adapters.dataset_files import DatasetFileError, UnsupportedDatasetFormatError
from rinse.application import CleaningPipeline, CleaningPipelineRequest, ProfileDataset, ProfileDatasetRequest
from rinse.domain import CleaningReport, ColumnTypeSuggestion, DuplicateGroup, ValidationIssue
from rinse.domain.entities import ExportArtifact, OperationResult
from rinse.domain.entities import Dataset
from rinse.domain.value_objects import CellChange, ColumnName, DatasetReference, RowIndex
from rinse.interfaces.cli import build_operations, report_with_artifacts


class CleaningOptionsDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    dedup: str = "none"
    dedup_columns: str = ""
    fuzzy_threshold: float = 92
    fuzzy_mode: str = "suggest"
    infer_types: bool = False
    type_columns: str = ""
    type_overrides: str = ""
    missing_policy: str = "keep"
    missing_columns: str = ""
    fill_value: str = ""
    validation: str = Field(default="", alias="validate")
    required_columns: str = ""
    range_columns: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    positive_columns: str = ""
    allowed_columns: str = ""
    allowed_values: str = ""
    valid_email_columns: str = ""
    parseable_date_columns: str = ""
    validation_date_format: str = "%Y-%m-%d,%m/%d/%Y"
    normalize: str = ""
    normalize_columns: str = ""
    text_columns: str = ""
    email_columns: str = ""
    date_columns: str = ""
    phone_columns: str = ""
    text_case: str = "keep"
    date_input_format: str = "%m/%d/%Y"
    date_output_format: str = "%Y-%m-%d"
    phone_region: str = "US"


class PreviewRequestDto(BaseModel):
    options: CleaningOptionsDto = Field(default_factory=CleaningOptionsDto)
    limit: int = Field(default=20, ge=1, le=100)


class CleanJobRequestDto(BaseModel):
    dataset_id: str
    options: CleaningOptionsDto = Field(default_factory=CleaningOptionsDto)
    output_format: str = "json"
    report_format: str = "json"


@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    filename: str
    path: Path


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    dataset_id: str
    status: str
    output_path: Optional[Path] = None
    report_path: Optional[Path] = None
    report: Optional[CleaningReport] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    owner_id: str
    label: str
    kind: str
    path: Path


class ApiStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.database_path = root / "metadata.sqlite3"
        self.root.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                "create table if not exists datasets (dataset_id text primary key, filename text not null, path text not null)"
            )
            connection.execute(
                "create table if not exists jobs (job_id text primary key, dataset_id text not null, status text not null, output_path text, report_path text, report_json text, error text)"
            )
            connection.execute(
                "create table if not exists artifacts (artifact_id text primary key, owner_id text not null, label text not null, kind text not null, path text not null)"
            )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def save_upload(self, upload: UploadFile, content: bytes) -> DatasetRecord:
        filename = Path(upload.filename or "dataset.csv").name
        dataset_id = uuid4().hex
        path = self.root / "datasets" / dataset_id / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        record = DatasetRecord(dataset_id=dataset_id, filename=filename, path=path)
        with self.connect() as connection:
            connection.execute(
                "insert into datasets (dataset_id, filename, path) values (?, ?, ?)",
                (record.dataset_id, record.filename, str(record.path)),
            )
        self.save_artifact(
            ArtifactRecord(
                artifact_id=uuid4().hex,
                owner_id=dataset_id,
                label="Original upload",
                kind=path.suffix.lstrip(".") or "file",
                path=path,
            )
        )
        return record

    def dataset(self, dataset_id: str) -> DatasetRecord:
        with self.connect() as connection:
            row = connection.execute(
                "select dataset_id, filename, path from datasets where dataset_id = ?",
                (dataset_id,),
            ).fetchone()
        if row is None:
            raise KeyError(dataset_id)
        return DatasetRecord(dataset_id=row["dataset_id"], filename=row["filename"], path=Path(row["path"]))

    def save_job(self, record: JobRecord) -> JobRecord:
        with self.connect() as connection:
            connection.execute(
                "insert into jobs (job_id, dataset_id, status, output_path, report_path, report_json, error) values (?, ?, ?, ?, ?, ?, ?)",
                (
                    record.job_id,
                    record.dataset_id,
                    record.status,
                    str(record.output_path) if record.output_path else None,
                    str(record.report_path) if record.report_path else None,
                    json.dumps(record.report.to_dict(), ensure_ascii=False) if record.report else None,
                    record.error,
                ),
            )
        return record

    def update_job(self, record: JobRecord) -> JobRecord:
        with self.connect() as connection:
            connection.execute(
                "update jobs set status = ?, output_path = ?, report_path = ?, report_json = ?, error = ? where job_id = ?",
                (
                    record.status,
                    str(record.output_path) if record.output_path else None,
                    str(record.report_path) if record.report_path else None,
                    json.dumps(record.report.to_dict(), ensure_ascii=False) if record.report else None,
                    record.error,
                    record.job_id,
                ),
            )
        return record

    def job(self, job_id: str) -> JobRecord:
        with self.connect() as connection:
            row = connection.execute(
                "select job_id, dataset_id, status, output_path, report_path, report_json, error from jobs where job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return JobRecord(
            job_id=row["job_id"],
            dataset_id=row["dataset_id"],
            status=row["status"],
            output_path=Path(row["output_path"]) if row["output_path"] else None,
            report_path=Path(row["report_path"]) if row["report_path"] else None,
            report=report_from_dict(json.loads(row["report_json"])) if row["report_json"] else None,
            error=row["error"],
        )

    def save_artifact(self, record: ArtifactRecord) -> ArtifactRecord:
        with self.connect() as connection:
            connection.execute(
                "insert into artifacts (artifact_id, owner_id, label, kind, path) values (?, ?, ?, ?, ?)",
                (record.artifact_id, record.owner_id, record.label, record.kind, str(record.path)),
            )
        return record

    def artifacts(self, owner_id: str) -> list[ArtifactRecord]:
        with self.connect() as connection:
            rows = connection.execute(
                "select artifact_id, owner_id, label, kind, path from artifacts where owner_id = ? order by label",
                (owner_id,),
            ).fetchall()
        return [
            ArtifactRecord(
                artifact_id=row["artifact_id"],
                owner_id=row["owner_id"],
                label=row["label"],
                kind=row["kind"],
                path=Path(row["path"]),
            )
            for row in rows
        ]


class ApiService:
    def __init__(self, store: ApiStore, executor: Optional[ThreadPoolExecutor] = None) -> None:
        self.store = store
        self.executor = executor or ThreadPoolExecutor(max_workers=2)
        self.reader = PandasDatasetReader()
        self.writer = PandasDatasetWriter()

    def upload(self, upload: UploadFile, content: bytes) -> dict[str, object]:
        record = self.store.save_upload(upload, content)
        dataset = self.reader.read(DatasetReference(str(record.path)))
        return self.dataset_payload(record, dataset)

    def profile(self, dataset_id: str) -> dict[str, object]:
        record = self.store.dataset(dataset_id)
        result = ProfileDataset(self.reader).execute(ProfileDatasetRequest(DatasetReference(str(record.path))))
        return {
            "dataset_id": record.dataset_id,
            "filename": record.filename,
            "rows": result.rows,
            "columns": result.columns,
            "column_names": list(result.column_names),
        }

    def preview(self, dataset_id: str, request: PreviewRequestDto) -> dict[str, object]:
        record = self.store.dataset(dataset_id)
        dataset = self.reader.read(DatasetReference(str(record.path)))
        cleaned, report = self.clean_dataset(dataset, request.options)
        return {
            "dataset_id": dataset_id,
            "rows": self.rows(cleaned, request.limit),
            "report": report.to_dict(),
            "preview": True,
        }

    def clean(self, request: CleanJobRequestDto) -> dict[str, object]:
        self.store.dataset(request.dataset_id)
        job_id = uuid4().hex
        job = self.store.save_job(JobRecord(job_id=job_id, dataset_id=request.dataset_id, status="queued"))
        self.executor.submit(self.run_clean_job, job_id, request)
        return self.job_payload(job)

    def run_clean_job(self, job_id: str, request: CleanJobRequestDto) -> None:
        self.store.update_job(JobRecord(job_id=job_id, dataset_id=request.dataset_id, status="running"))
        try:
            self.complete_clean_job(job_id, request)
        except Exception as error:
            self.store.update_job(
                JobRecord(
                    job_id=job_id,
                    dataset_id=request.dataset_id,
                    status="failed",
                    error=str(error),
                )
            )

    def complete_clean_job(self, job_id: str, request: CleanJobRequestDto) -> None:
        record = self.store.dataset(request.dataset_id)
        dataset = self.reader.read(DatasetReference(str(record.path)))
        cleaned, report = self.clean_dataset(dataset, request.options)
        output_path = self.output_artifact_path(job_id, request.output_format)
        report_path = self.report_artifact_path(job_id, request.report_format)
        self.writer.write(cleaned, DatasetReference(str(output_path)))
        report = report_with_artifacts(report, out=str(output_path), report_path=str(report_path))
        self.write_report(report, report_path)
        self.store.save_artifact(
            ArtifactRecord(
                artifact_id=uuid4().hex,
                owner_id=job_id,
                label="Clean output",
                kind=output_path.suffix.lstrip(".") or "file",
                path=output_path,
            )
        )
        self.store.save_artifact(
            ArtifactRecord(
                artifact_id=uuid4().hex,
                owner_id=job_id,
                label="Audit report",
                kind=report_path.suffix.lstrip(".") or "report",
                path=report_path,
            )
        )
        self.store.update_job(
            JobRecord(
                job_id=job_id,
                dataset_id=request.dataset_id,
                status="completed",
                output_path=output_path,
                report_path=report_path,
                report=report,
            )
        )

    def job_status(self, job_id: str) -> dict[str, object]:
        return self.job_payload(self.store.job(job_id))

    def job_result(self, job_id: str) -> dict[str, object]:
        job = self.store.job(job_id)
        if job.status != "completed" or job.output_path is None:
            raise ValueError(f"Job is not completed: {job.status}")
        dataset = self.reader.read(DatasetReference(str(job.output_path)))
        return {
            "job_id": job.job_id,
            "dataset_id": job.dataset_id,
            "rows": self.rows(dataset, dataset.row_count),
        }

    def job_report(self, job_id: str) -> dict[str, object]:
        job = self.store.job(job_id)
        if job.status != "completed" or job.report is None:
            raise ValueError(f"Job is not completed: {job.status}")
        return {"job_id": job.job_id, "report": job.report.to_dict()}

    def clean_dataset(self, dataset: Dataset, options: CleaningOptionsDto) -> tuple[Dataset, CleaningReport]:
        payload = options.model_dump()
        payload["validate"] = payload.pop("validation")
        operations = build_operations(**payload)
        if not operations:
            return dataset, CleaningReport(rows_before=dataset.row_count, rows_after=dataset.row_count)
        result = CleaningPipeline(tuple(operations)).run(CleaningPipelineRequest(dataset=dataset, preview=True))
        return result.dataset, result.report

    def output_artifact_path(self, job_id: str, suffix: str) -> Path:
        normalized = suffix.strip().lower().lstrip(".") or "json"
        if normalized not in {"csv", "xlsx", "json"}:
            raise ValueError(f"Unsupported clean output format: {suffix}")
        return self.store.root / "jobs" / job_id / f"clean.{normalized}"

    def report_artifact_path(self, job_id: str, suffix: str) -> Path:
        normalized = suffix.strip().lower().lstrip(".") or "json"
        if normalized == "htm":
            normalized = "html"
        if normalized not in {"json", "html"}:
            raise ValueError(f"Unsupported report format: {suffix}")
        return self.store.root / "jobs" / job_id / f"report.{normalized}"

    def write_report(self, report: CleaningReport, path: Path) -> None:
        if path.suffix == ".html":
            HtmlReportWriter().write(report, DatasetReference(str(path)))
            return
        if path.suffix == ".json":
            JsonReportWriter().write(report, DatasetReference(str(path)))
            return
        raise ValueError("Report format must be .json or .html")

    def dataset_payload(self, record: DatasetRecord, dataset: Dataset) -> dict[str, object]:
        return {
            "dataset_id": record.dataset_id,
            "filename": record.filename,
            "rows": dataset.row_count,
            "columns": dataset.column_count,
            "column_names": [column.value for column in dataset.columns],
        }

    def job_payload(self, job: JobRecord) -> dict[str, object]:
        return {
            "job_id": job.job_id,
            "dataset_id": job.dataset_id,
            "status": job.status,
            "error": job.error,
            "artifacts": [self.artifact_payload(artifact) for artifact in self.store.artifacts(job.job_id)],
            "result_url": f"/api/jobs/{job.job_id}/result",
            "report_url": f"/api/jobs/{job.job_id}/report",
            "download_url": f"/api/jobs/{job.job_id}/download",
        }

    def artifact_payload(self, artifact: ArtifactRecord) -> dict[str, object]:
        return {
            "artifact_id": artifact.artifact_id,
            "label": artifact.label,
            "kind": artifact.kind,
            "filename": artifact.path.name,
        }

    def rows(self, dataset: Dataset, limit: int) -> list[dict[str, object]]:
        columns = [column.value for column in dataset.columns]
        return [
            {column: row.get(column) for column in columns}
            for row in dataset.rows[:limit]
        ]


def create_app(storage_root: Optional[Path] = None, executor: Optional[ThreadPoolExecutor] = None) -> FastAPI:
    temporary_directory = None
    if storage_root is None:
        temporary_directory = TemporaryDirectory()
        storage_root = Path(temporary_directory.name)
    service = ApiService(ApiStore(storage_root), executor=executor)
    app = FastAPI(title="Rinse API")
    app.state.temporary_directory = temporary_directory

    @app.exception_handler(KeyError)
    async def key_error_handler(request, error):
        return error_response(404, "not_found", "Requested dataset or job was not found")

    @app.exception_handler(ValueError)
    async def value_error_handler(request, error):
        return error_response(400, "invalid_request", str(error))

    @app.exception_handler(DatasetFileError)
    async def dataset_file_error_handler(request, error):
        return error_response(400, "dataset_file_error", str(error))

    @app.exception_handler(UnsupportedDatasetFormatError)
    async def unsupported_format_handler(request, error):
        return error_response(400, "unsupported_dataset_format", str(error))

    @app.post("/api/datasets/upload")
    async def upload_dataset(file: UploadFile = File(...)):
        return service.upload(file, await file.read())

    @app.get("/api/datasets/{dataset_id}/profile")
    async def profile_dataset(dataset_id: str):
        return service.profile(dataset_id)

    @app.post("/api/datasets/{dataset_id}/preview")
    async def preview_dataset(dataset_id: str, request: PreviewRequestDto):
        return service.preview(dataset_id, request)

    @app.post("/api/jobs/clean")
    async def clean_dataset(request: CleanJobRequestDto):
        return service.clean(request)

    @app.get("/api/jobs/{job_id}")
    async def job_status(job_id: str):
        return service.job_status(job_id)

    @app.get("/api/jobs/{job_id}/result")
    async def job_result(job_id: str):
        return service.job_result(job_id)

    @app.get("/api/jobs/{job_id}/report")
    async def job_report(job_id: str):
        return service.job_report(job_id)

    @app.get("/api/jobs/{job_id}/download")
    async def job_download(job_id: str):
        job = service.store.job(job_id)
        if job.status != "completed" or job.output_path is None:
            raise ValueError(f"Job is not completed: {job.status}")
        return FileResponse(job.output_path, filename=job.output_path.name)

    return app


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": {"code": code, "message": message}})


app = create_app()


def report_from_dict(content: dict[str, object]) -> CleaningReport:
    return CleaningReport(
        rows_before=int(content["rows_before"]),
        rows_after=int(content["rows_after"]),
        operation_results=tuple(
            OperationResult(
                name=str(operation["name"]),
                rows_removed=int(operation["rows_removed"]),
                cells_changed=tuple(
                    CellChange(
                        row=RowIndex(int(change["row"])),
                        column=ColumnName(str(change["column"])),
                        before=change["before"],
                        after=change["after"],
                        reason=str(change["reason"]),
                    )
                    for change in operation["cell_changes"]
                ),
                validation_issues=tuple(
                    ValidationIssue(
                        row=RowIndex(int(issue["row"])),
                        column=ColumnName(str(issue["column"])),
                        rule=str(issue["rule"]),
                        value=issue["value"],
                        message=str(issue["message"]),
                    )
                    for issue in operation["issues"]
                ),
                duplicate_groups=tuple(
                    DuplicateGroup(
                        kept_row=RowIndex(int(group["kept_row"])),
                        matched_rows=tuple(RowIndex(int(row)) for row in group["matched_rows"]),
                        score=float(group["score"]),
                        reason=str(group["reason"]),
                    )
                    for group in operation["duplicates"]
                ),
                type_suggestions=tuple(
                    ColumnTypeSuggestion(
                        column=ColumnName(str(suggestion["column"])),
                        suggested_type=str(suggestion["suggested_type"]),
                        confidence=float(suggestion["confidence"]),
                        reason=str(suggestion["reason"]),
                    )
                    for suggestion in operation["type_suggestions"]
                ),
            )
            for operation in content["operations"]
        ),
        export_artifacts=tuple(
            ExportArtifact(
                label=str(artifact["label"]),
                location=str(artifact["location"]),
                kind=str(artifact["kind"]),
            )
            for artifact in content["export_artifacts"]
        ),
    )
