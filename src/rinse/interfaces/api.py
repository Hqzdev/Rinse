from dataclasses import dataclass
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
from rinse.domain import CleaningReport
from rinse.domain.entities import Dataset
from rinse.domain.value_objects import DatasetReference
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
    output_path: Path
    report_path: Path
    report: CleaningReport


class ApiStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.datasets: dict[str, DatasetRecord] = {}
        self.jobs: dict[str, JobRecord] = {}
        self.root.mkdir(parents=True, exist_ok=True)

    def save_upload(self, upload: UploadFile, content: bytes) -> DatasetRecord:
        filename = Path(upload.filename or "dataset.csv").name
        dataset_id = uuid4().hex
        path = self.root / "datasets" / dataset_id / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        record = DatasetRecord(dataset_id=dataset_id, filename=filename, path=path)
        self.datasets[dataset_id] = record
        return record

    def dataset(self, dataset_id: str) -> DatasetRecord:
        record = self.datasets.get(dataset_id)
        if record is None:
            raise KeyError(dataset_id)
        return record

    def save_job(self, record: JobRecord) -> JobRecord:
        self.jobs[record.job_id] = record
        return record

    def job(self, job_id: str) -> JobRecord:
        record = self.jobs.get(job_id)
        if record is None:
            raise KeyError(job_id)
        return record


class ApiService:
    def __init__(self, store: ApiStore) -> None:
        self.store = store
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
        record = self.store.dataset(request.dataset_id)
        dataset = self.reader.read(DatasetReference(str(record.path)))
        cleaned, report = self.clean_dataset(dataset, request.options)
        job_id = uuid4().hex
        output_path = self.output_artifact_path(job_id, request.output_format)
        report_path = self.report_artifact_path(job_id, request.report_format)
        self.writer.write(cleaned, DatasetReference(str(output_path)))
        report = report_with_artifacts(report, out=str(output_path), report_path=str(report_path))
        self.write_report(report, report_path)
        job = self.store.save_job(
            JobRecord(
                job_id=job_id,
                dataset_id=request.dataset_id,
                status="completed",
                output_path=output_path,
                report_path=report_path,
                report=report,
            )
        )
        return self.job_payload(job)

    def job_status(self, job_id: str) -> dict[str, object]:
        return self.job_payload(self.store.job(job_id))

    def job_result(self, job_id: str) -> dict[str, object]:
        job = self.store.job(job_id)
        dataset = self.reader.read(DatasetReference(str(job.output_path)))
        return {
            "job_id": job.job_id,
            "dataset_id": job.dataset_id,
            "rows": self.rows(dataset, dataset.row_count),
        }

    def job_report(self, job_id: str) -> dict[str, object]:
        job = self.store.job(job_id)
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
            "result_url": f"/api/jobs/{job.job_id}/result",
            "report_url": f"/api/jobs/{job.job_id}/report",
            "download_url": f"/api/jobs/{job.job_id}/download",
        }

    def rows(self, dataset: Dataset, limit: int) -> list[dict[str, object]]:
        columns = [column.value for column in dataset.columns]
        return [
            {column: row.get(column) for column in columns}
            for row in dataset.rows[:limit]
        ]


def create_app(storage_root: Optional[Path] = None) -> FastAPI:
    temporary_directory = None
    if storage_root is None:
        temporary_directory = TemporaryDirectory()
        storage_root = Path(temporary_directory.name)
    service = ApiService(ApiStore(storage_root))
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
        return FileResponse(job.output_path, filename=job.output_path.name)

    return app


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": {"code": code, "message": message}})


app = create_app()
