export type CellState = "clean" | "warn" | "danger" | "fixed" | "missing" | "duplicate";

export type DataCell = {
  value: string;
  state?: CellState;
};

export type DataRow = {
  id: string;
  cells: DataCell[];
  duplicate?: boolean;
};

export type Metric = {
  label: string;
  value: string;
  tone?: "success" | "warning" | "danger";
};

export const columns = ["name", "email", "signup", "amount", "status"];

export const dirtyRows: DataRow[] = [
  {
    id: "C-001",
    cells: [
      { value: "  Alice   Smith ", state: "warn" },
      { value: " ALICE@example.COM ", state: "warn" },
      { value: "01/02/2026", state: "warn" },
      { value: "100" },
      { value: "active" }
    ]
  },
  {
    id: "C-001-DUP",
    duplicate: true,
    cells: [
      { value: "alice smith", state: "duplicate" },
      { value: "alice@example.com", state: "duplicate" },
      { value: "2026-01-02" },
      { value: "100" },
      { value: "active" }
    ]
  },
  {
    id: "C-002",
    cells: [
      { value: "Bob   Stone", state: "warn" },
      { value: "bad-email", state: "danger" },
      { value: "broken", state: "danger" },
      { value: "", state: "missing" },
      { value: "draft", state: "danger" }
    ]
  },
  {
    id: "C-003",
    cells: [
      { value: "Carla Gomez" },
      { value: "carla@example.com" },
      { value: "02/14/2026", state: "warn" },
      { value: "-5", state: "danger" },
      { value: "blocked" }
    ]
  }
];

export const cleanRows: DataRow[] = [
  {
    id: "C-001",
    cells: [
      { value: "Alice Smith", state: "fixed" },
      { value: "alice@example.com", state: "fixed" },
      { value: "2026-01-02", state: "fixed" },
      { value: "100" },
      { value: "active" }
    ]
  },
  {
    id: "C-002",
    cells: [
      { value: "Bob Stone", state: "fixed" },
      { value: "bad-email", state: "danger" },
      { value: "broken", state: "danger" },
      { value: "1", state: "fixed" },
      { value: "draft", state: "danger" }
    ]
  },
  {
    id: "C-003",
    cells: [
      { value: "Carla Gomez" },
      { value: "carla@example.com" },
      { value: "2026-02-14", state: "fixed" },
      { value: "-5", state: "danger" },
      { value: "blocked" }
    ]
  }
];

export const processSteps = [
  {
    index: "01",
    title: "Upload dirty data",
    body: "CSV and XLSX files are parsed into a tabular dataset, then profiled before any destructive operation runs."
  },
  {
    index: "02",
    title: "Compose operations",
    body: "Choose normalization, missing-value handling, type suggestions, validation, exact deduplication, or fuzzy deduplication."
  },
  {
    index: "03",
    title: "Export with evidence",
    body: "Rinse writes clean CSV, XLSX, or JSON and a machine-readable audit report with every meaningful change."
  }
];

export const pipelineSteps = [
  { name: "type inference", count: "2 suggestions" },
  { name: "missing values", count: "1 filled" },
  { name: "text normalization", count: "2 cells" },
  { name: "email normalization", count: "1 cell, 1 issue" },
  { name: "date normalization", count: "2 cells, 1 issue" },
  { name: "phone normalization", count: "3 cells, 1 issue" },
  { name: "fuzzy deduplication", count: "1 row removed" }
];

export const reportMetrics: Metric[] = [
  { label: "Rows processed", value: "5" },
  { label: "Rows exported", value: "4", tone: "success" },
  { label: "Rows removed", value: "1", tone: "warning" },
  { label: "Cells changed", value: "9", tone: "success" },
  { label: "Validation issues", value: "8", tone: "danger" },
  { label: "Duplicate groups", value: "1", tone: "warning" }
];

export const reportIssues = [
  { row: "C-002", rule: "valid_email", value: "bad-email" },
  { row: "C-002", rule: "parseable_date", value: "broken" },
  { row: "C-003", rule: "positive_number", value: "-5" },
  { row: "C-004", rule: "required", value: "email missing" }
];

export const architectureLayers = [
  {
    title: "Domain",
    detail: "Datasets, operations, duplicate groups, validation issues, and report data."
  },
  {
    title: "Application",
    detail: "Composable pipeline orchestration that CLI, API, and web surfaces can reuse."
  },
  {
    title: "Adapters",
    detail: "Pandas file IO, JSON and HTML reports, phone normalization, and RapidFuzz similarity."
  },
  {
    title: "Interfaces",
    detail: "Typer CLI, FastAPI endpoints, and a Next.js surface over the same cleaning pipeline."
  }
];
