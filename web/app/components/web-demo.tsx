"use client";

import { AlertCircle, Check, Database, Download, FileDown, Loader2, Play, RefreshCcw, Upload } from "lucide-react";
import { ChangeEvent, useMemo, useState } from "react";

type DatasetProfile = {
  dataset_id: string;
  filename: string;
  rows: number;
  columns: number;
  column_names: string[];
};

type PreviewPayload = {
  rows: DataRecord[];
  report: CleaningReport;
};

type JobPayload = {
  job_id: string;
  dataset_id: string;
  status: "queued" | "running" | "completed" | "failed";
  error: string | null;
  artifacts: ArtifactPayload[];
  result_url: string;
  report_url: string;
  report_download_url: string;
  download_url: string;
};

type ArtifactPayload = {
  artifact_id: string;
  label: string;
  kind: string;
  filename: string;
};

type CleaningReport = {
  rows_before: number;
  rows_after: number;
  rows_removed: number;
  cells_changed: number;
  validation_issue_count: number;
  duplicate_group_count: number;
  operations: OperationReport[];
};

type OperationReport = {
  name: string;
  rows_removed: number;
  cells_changed: number;
  validation_issues: number;
  duplicate_groups: number;
  cell_changes: CellChangePayload[];
  issues: ValidationIssuePayload[];
  duplicates: DuplicatePayload[];
};

type CellChangePayload = {
  row: number;
  column: string;
  before: unknown;
  after: unknown;
  reason: string;
};

type ValidationIssuePayload = {
  row: number;
  column: string;
  rule: string;
  value: unknown;
  message: string;
};

type DuplicatePayload = {
  kept_row: number;
  matched_rows: number[];
  score: number;
  reason: string;
};

type DataRecord = Record<string, unknown>;

type OperationKey = "text" | "email" | "date" | "dedup" | "missing" | "types";

type RequestOptions = {
  normalize: string;
  normalize_columns: string;
  text_columns: string;
  email_columns: string;
  date_columns: string;
  text_case: string;
  date_input_format: string;
  date_output_format: string;
  dedup: string;
  dedup_columns: string;
  fuzzy_threshold: number;
  fuzzy_mode: string;
  infer_types: boolean;
  type_columns: string;
  missing_policy: string;
  missing_columns: string;
  fill_value: string;
  validate: string;
  required_columns: string;
  valid_email_columns: string;
  parseable_date_columns: string;
};

const sampleCsv = `customer_id,name,email,signup_date,amount,status
C-001,  Alice   Smith , ALICE@example.COM ,01/02/2026,100,active
C-001-DUP,alice smith,alice@example.com,2026-01-02,100,active
C-002,Bob   Stone,bad-email,broken,,draft
C-003,Carla Gomez,carla@example.com,02/14/2026,-5,blocked
C-004,,missing@example.com,03/01/2026,42,active`;

const sampleFile = new File([sampleCsv], "dirty-customers.csv", { type: "text/csv" });

const operationLabels: Record<OperationKey, string> = {
  text: "Text",
  email: "Email",
  date: "Dates",
  dedup: "Fuzzy dedup",
  missing: "Missing",
  types: "Types"
};

const defaultOperations: OperationKey[] = ["text", "email", "date", "dedup", "missing", "types"];

export function WebDemo() {
  const apiBase = process.env.NEXT_PUBLIC_RINSE_API_URL ?? "http://127.0.0.1:8000";
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [sourceRows, setSourceRows] = useState<DataRecord[]>([]);
  const [preview, setPreview] = useState<PreviewPayload | null>(null);
  const [job, setJob] = useState<JobPayload | null>(null);
  const [recentJobs, setRecentJobs] = useState<JobPayload[]>([]);
  const [selectedOperations, setSelectedOperations] = useState<OperationKey[]>(defaultOperations);
  const [fuzzyThreshold, setFuzzyThreshold] = useState(90);
  const [status, setStatus] = useState("Waiting for a CSV or XLSX file.");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const columns = profile?.column_names ?? [];
  const changedCells = useMemo(() => changedCellKeys(preview?.report), [preview]);

  async function uploadDataset(file: File) {
    setIsBusy(true);
    setError(null);
    setStatus("Uploading and profiling dataset.");
    try {
      const form = new FormData();
      form.append("file", file);
      const uploaded = await request<DatasetProfile>(apiBase, "/api/datasets/upload", { method: "POST", body: form });
      setProfile(uploaded);
      setJob(null);
      setPreview(null);
      setStatus("Loading original preview.");
      const original = await request<PreviewPayload>(apiBase, `/api/datasets/${uploaded.dataset_id}/preview`, {
        method: "POST",
        body: JSON.stringify({ options: {}, limit: 8 }),
        headers: { "Content-Type": "application/json" }
      });
      setSourceRows(original.rows);
      setStatus("Dataset ready. Run preview or start a clean job.");
    } catch (caught) {
      setError(messageFrom(caught));
      setStatus("Upload failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function previewDataset() {
    if (!profile) {
      return;
    }
    setIsBusy(true);
    setError(null);
    setStatus("Running preview through FastAPI.");
    try {
      const payload = await request<PreviewPayload>(apiBase, `/api/datasets/${profile.dataset_id}/preview`, {
        method: "POST",
        body: JSON.stringify({ options: buildOptions(columns, selectedOperations, fuzzyThreshold), limit: 8 }),
        headers: { "Content-Type": "application/json" }
      });
      setPreview(payload);
      setStatus("Preview ready. Before/after and report came from the API.");
    } catch (caught) {
      setError(messageFrom(caught));
      setStatus("Preview failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function cleanDataset() {
    if (!profile) {
      return;
    }
    setIsBusy(true);
    setError(null);
    setStatus("Queueing clean job.");
    try {
      const queued = await request<JobPayload>(apiBase, "/api/jobs/clean", {
        method: "POST",
        body: JSON.stringify({
          dataset_id: profile.dataset_id,
          options: buildOptions(columns, selectedOperations, fuzzyThreshold),
          output_format: "json",
          report_format: "html"
        }),
        headers: { "Content-Type": "application/json" }
      });
      setJob(queued);
      const completed = await pollJob(apiBase, queued.job_id, setStatus);
      setJob(completed);
      setRecentJobs((jobs) => [completed, ...jobs.filter((item) => item.job_id !== completed.job_id)].slice(0, 4));
      if (completed.status === "failed") {
        setError(completed.error ?? "Clean job failed.");
        return;
      }
      const reportPayload = await request<{ report: CleaningReport }>(apiBase, completed.report_url);
      setPreview((current) => current && { ...current, report: reportPayload.report });
      setStatus("Clean job completed. Downloads are ready.");
    } catch (caught) {
      setError(messageFrom(caught));
      setStatus("Clean job failed.");
    } finally {
      setIsBusy(false);
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    if (file) {
      void uploadDataset(file);
    }
  }

  function toggleOperation(operation: OperationKey) {
    setSelectedOperations((current) =>
      current.includes(operation) ? current.filter((item) => item !== operation) : [...current, operation]
    );
  }

  return (
    <section className="demo-section" id="demo">
      <div className="wrap demo-shell">
        <div className="demo-intro">
          <span className="eyebrow">Live API workflow</span>
          <h1>Upload messy data, preview the cleanup, then export the evidence.</h1>
          <p>
            This screen calls the FastAPI adapter directly. The browser handles selection and display; the cleaning logic stays in the Python pipeline.
          </p>
          <div className="demo-actions">
            <label className="demo-upload">
              <Upload size={16} />
              <span>Upload file</span>
              <input accept=".csv,.xlsx" onChange={handleFileChange} type="file" />
            </label>
            <button className="demo-button secondary" disabled={isBusy} onClick={() => uploadDataset(sampleFile)} type="button">
              <Database size={16} />
              <span>Use sample</span>
            </button>
            <button className="demo-button" disabled={!profile || isBusy} onClick={previewDataset} type="button">
              {isBusy ? <Loader2 className="spin-icon" size={16} /> : <RefreshCcw size={16} />}
              <span>Preview</span>
            </button>
            <button className="demo-button primary" disabled={!profile || isBusy} onClick={cleanDataset} type="button">
              {isBusy ? <Loader2 className="spin-icon" size={16} /> : <Play size={16} />}
              <span>Clean</span>
            </button>
          </div>
          <div className={`demo-status ${error ? "demo-status-error" : ""}`}>
            {error ? <AlertCircle size={15} /> : <Check size={15} />}
            <span>{error ?? status}</span>
          </div>
        </div>
        <div className="demo-control-panel">
          <div className="demo-card">
            <div className="demo-card-head">
              <span>Dataset</span>
              <b>{profile ? `${profile.rows} rows / ${profile.columns} columns` : "No file"}</b>
            </div>
            <div className="dataset-name">{profile?.filename ?? "Upload a CSV/XLSX or load the sample dataset"}</div>
            <div className="column-chips">
              {(columns.length ? columns : ["customer_id", "name", "email", "signup_date", "amount", "status"]).map((column) => (
                <span key={column}>{column}</span>
              ))}
            </div>
          </div>
          <div className="demo-card">
            <div className="demo-card-head">
              <span>Operations</span>
              <b>{selectedOperations.length} selected</b>
            </div>
            <div className="operation-grid">
              {defaultOperations.map((operation) => (
                <label className="operation-toggle" key={operation}>
                  <input checked={selectedOperations.includes(operation)} onChange={() => toggleOperation(operation)} type="checkbox" />
                  <span>{operationLabels[operation]}</span>
                </label>
              ))}
            </div>
            <label className="range-field">
              <span>Fuzzy threshold</span>
              <b>{fuzzyThreshold}</b>
              <input max="100" min="70" onChange={(event) => setFuzzyThreshold(Number(event.currentTarget.value))} type="range" value={fuzzyThreshold} />
            </label>
          </div>
          <div className="demo-card recent-card">
            <div className="demo-card-head">
              <span>Recent jobs</span>
              <b>{recentJobs.length}</b>
            </div>
            {recentJobs.length ? (
              recentJobs.map((item) => (
                <button className="recent-job" key={item.job_id} onClick={() => setJob(item)} type="button">
                  <span>{item.job_id.slice(0, 8)}</span>
                  <b>{item.status}</b>
                </button>
              ))
            ) : (
              <p>No completed jobs yet.</p>
            )}
          </div>
        </div>
        <div className="preview-grid">
          <LiveTable changedCells={new Set()} columns={columns} rows={sourceRows} title="Before" />
          <LiveTable changedCells={changedCells} columns={columns} rows={preview?.rows ?? []} title="After" />
        </div>
        <div className="report-grid">
          <ReportSummary report={preview?.report ?? null} />
          <div className="demo-card downloads-card">
            <div className="demo-card-head">
              <span>Downloads</span>
              <b>{job?.status ?? "waiting"}</b>
            </div>
            <div className="artifact-list">
              {job?.artifacts.length ? (
                job.artifacts.map((artifact) => (
                  <span key={artifact.artifact_id}>{artifact.label}: {artifact.filename}</span>
                ))
              ) : (
                <span>Run a clean job to create artifacts.</span>
              )}
            </div>
            <div className="download-actions">
              <a className={!job || job.status !== "completed" ? "disabled-link" : ""} href={job ? absoluteUrl(apiBase, job.download_url) : "#"}>
                <Download size={16} />
                <span>Clean file</span>
              </a>
              <a className={!job || job.status !== "completed" ? "disabled-link" : ""} href={job ? absoluteUrl(apiBase, job.report_download_url) : "#"}>
                <FileDown size={16} />
                <span>Audit report</span>
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function LiveTable({ changedCells, columns, rows, title }: { changedCells: Set<string>; columns: string[]; rows: DataRecord[]; title: string }) {
  const visibleColumns = columns.length ? columns : ["customer_id", "name", "email", "signup_date", "amount", "status"];
  return (
    <div className="live-table-card">
      <div className="demo-card-head">
        <span>{title}</span>
        <b>{rows.length ? `${rows.length} rows` : "waiting"}</b>
      </div>
      <div className="live-table-scroll">
        <div className="live-table" style={{ gridTemplateColumns: `72px repeat(${visibleColumns.length}, minmax(130px, 1fr))` }}>
          <span className="live-head">row</span>
          {visibleColumns.map((column) => (
            <span className="live-head" key={column}>{column}</span>
          ))}
          {rows.length ? rows.flatMap((row, rowIndex) => [
            <span className="live-row-id" key={`${title}-${rowIndex}-index`}>{rowIndex + 1}</span>,
            ...visibleColumns.map((column) => (
              <span className={changedCells.has(`${rowIndex}:${column}`) ? "live-cell changed" : "live-cell"} key={`${title}-${rowIndex}-${column}`}>
                {formatValue(row[column])}
              </span>
            ))
          ]) : (
            <span className="live-empty">No preview data yet.</span>
          )}
        </div>
      </div>
    </div>
  );
}

function ReportSummary({ report }: { report: CleaningReport | null }) {
  const operations = report?.operations ?? [];
  const issues = operations.flatMap((operation) => operation.issues.map((issue) => ({ ...issue, operation: operation.name }))).slice(0, 5);
  const duplicates = operations.flatMap((operation) => operation.duplicates.map((duplicate) => ({ ...duplicate, operation: operation.name }))).slice(0, 3);
  return (
    <div className="demo-card report-live-card">
      <div className="demo-card-head">
        <span>Report</span>
        <b>{report ? "generated" : "waiting"}</b>
      </div>
      <div className="live-metrics">
        <Metric label="Rows in" value={report?.rows_before ?? 0} />
        <Metric label="Rows out" value={report?.rows_after ?? 0} />
        <Metric label="Removed" value={report?.rows_removed ?? 0} />
        <Metric label="Changed" value={report?.cells_changed ?? 0} />
        <Metric label="Issues" value={report?.validation_issue_count ?? 0} />
        <Metric label="Duplicates" value={report?.duplicate_group_count ?? 0} />
      </div>
      <div className="report-detail-grid">
        <div>
          <span className="detail-title">Validation issues</span>
          {issues.length ? issues.map((issue) => (
            <p key={`${issue.operation}-${issue.row}-${issue.column}-${issue.rule}`}>Row {issue.row + 1} / {issue.column}: {issue.message}</p>
          )) : <p>No issues reported yet.</p>}
        </div>
        <div>
          <span className="detail-title">Duplicate groups</span>
          {duplicates.length ? duplicates.map((duplicate) => (
            <p key={`${duplicate.operation}-${duplicate.kept_row}`}>Keep row {duplicate.kept_row + 1}, matched {duplicate.matched_rows.map((row) => row + 1).join(", ")} at {Math.round(duplicate.score)}.</p>
          )) : <p>No duplicate groups reported yet.</p>}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}

function buildOptions(columns: string[], operations: OperationKey[], fuzzyThreshold: number): RequestOptions {
  const textColumns = selectedColumns(columns, ["name", "status", "customer"]);
  const emailColumns = selectedColumns(columns, ["email"]);
  const dateColumns = selectedColumns(columns, ["date", "signup"]);
  const missingColumns = selectedColumns(columns, ["amount", "name", "email"]);
  const dedupColumns = selectedColumns(columns, ["name", "email"]);
  const normalize = [
    operations.includes("text") ? "text" : "",
    operations.includes("email") ? "email" : "",
    operations.includes("date") ? "date" : ""
  ].filter(Boolean).join(",");
  return {
    normalize,
    normalize_columns: "",
    text_columns: operations.includes("text") ? textColumns : "",
    email_columns: operations.includes("email") ? emailColumns : "",
    date_columns: operations.includes("date") ? dateColumns : "",
    text_case: "title",
    date_input_format: "%m/%d/%Y,%Y-%m-%d",
    date_output_format: "%Y-%m-%d",
    dedup: operations.includes("dedup") ? "fuzzy" : "none",
    dedup_columns: dedupColumns,
    fuzzy_threshold: fuzzyThreshold,
    fuzzy_mode: "suggest",
    infer_types: operations.includes("types"),
    type_columns: "",
    missing_policy: operations.includes("missing") ? "fill" : "keep",
    missing_columns: operations.includes("missing") ? missingColumns : "",
    fill_value: "1",
    validate: [
      operations.includes("email") ? "email" : "",
      operations.includes("date") ? "date" : ""
    ].filter(Boolean).join(","),
    required_columns: "",
    valid_email_columns: operations.includes("email") ? emailColumns : "",
    parseable_date_columns: operations.includes("date") ? dateColumns : ""
  };
}

function selectedColumns(columns: string[], tokens: string[]) {
  return columns.filter((column) => tokens.some((token) => column.toLowerCase().includes(token))).join(",");
}

function changedCellKeys(report: CleaningReport | null | undefined) {
  const keys = new Set<string>();
  report?.operations.forEach((operation) => {
    operation.cell_changes.forEach((change) => keys.add(`${change.row}:${change.column}`));
  });
  return keys;
}

async function pollJob(apiBase: string, jobId: string, setStatus: (status: string) => void) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const job = await request<JobPayload>(apiBase, `/api/jobs/${jobId}`);
    if (job.status === "completed" || job.status === "failed") {
      return job;
    }
    setStatus(`Job ${job.status}. Waiting for worker.`);
    await new Promise((resolve) => setTimeout(resolve, 350));
  }
  throw new Error("Timed out while waiting for job.");
}

async function request<T>(apiBase: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(absoluteUrl(apiBase, path), init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail?.message ?? `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function absoluteUrl(apiBase: string, path: string) {
  if (path.startsWith("http")) {
    return path;
  }
  return `${apiBase.replace(/\/$/, "")}${path}`;
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "NULL";
  }
  return String(value);
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Unknown error";
}
