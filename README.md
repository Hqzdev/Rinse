# Rinse

Rinse is an auditable data-cleaning tool for messy CSV and Excel files. It normalizes inconsistent values, validates data quality rules, detects exact and fuzzy duplicates, exports clean datasets, and produces a structured report that explains what changed.

The project is built as a product-grade cleaning engine rather than a one-off pandas script. The core workflow lives behind application use cases and ports, so the same behavior is available through the CLI, FastAPI adapter, and Next.js web interface.

## What Rinse Does

- Reads CSV and XLSX files and exports CSV, XLSX, or JSON.
- Normalizes text, whitespace, casing, dates, emails, and phone numbers.
- Detects exact duplicates and fuzzy duplicates with configurable safety controls.
- Infers probable column types without mutating data.
- Handles missing values through keep, drop, fill, mean, median, or mode policies.
- Validates required values, numeric ranges, positive numbers, allowed values, emails, and parseable dates.
- Generates JSON and HTML audit reports from structured run data.
- Exposes the same cleaning pipeline through CLI, API, and web interfaces.

## Quickstart

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
rinse --help
```

Run a basic clean:

```bash
rinse clean tests/fixtures/dirty_customers.csv \
  --out clean.json \
  --normalize text,email \
  --text-columns name \
  --email-columns email \
  --report report.html
```

Inspect a dataset before cleaning:

```bash
rinse profile tests/fixtures/dirty_realistic_customers.csv
```

## Architecture

Rinse uses a hexagonal architecture. Domain and application code are isolated from file formats, frameworks, storage, job execution, and UI concerns.

```text
src/rinse/
  domain/          entities, value objects, cleaning operations
  application/     use cases and pipeline orchestration
  ports/           interfaces for datasets, reports, jobs, and storage
  adapters/        pandas IO, report writers, similarity, phone formatting
  infrastructure/  implementation boundary for runtime services
  interfaces/      Typer CLI and FastAPI entrypoints
```

Boundary rules:

- `domain` does not import FastAPI, Typer, pandas, openpyxl, Redis, SQLAlchemy, or frontend code.
- `application` orchestrates workflows without knowing concrete readers, writers, storage, or web frameworks.
- CLI, API, report rendering, file IO, and web UI are delivery adapters around the same core pipeline.

This keeps the cleaning behavior testable and reusable instead of coupling it to a single interface.

## CLI

The CLI is built with Typer and calls application use cases instead of duplicating cleaning logic.

```bash
rinse clean tests/fixtures/dirty_customers.csv \
  --out clean.xlsx \
  --normalize text,email \
  --text-columns name \
  --email-columns email
```

Run validation and write a JSON report:

```bash
rinse clean tests/fixtures/dirty_customers.csv \
  --out clean.json \
  --validate required \
  --required-columns name,email \
  --report report.json
```

Run a fuller data-quality workflow:

```bash
rinse clean tests/fixtures/dirty_realistic_customers.csv \
  --out clean.json \
  --normalize text,email,date,phone \
  --text-columns name,status \
  --email-columns email \
  --date-columns signup_date \
  --phone-columns phone \
  --infer-types \
  --missing-policy fill \
  --missing-columns amount \
  --fill-value 1 \
  --validate required,email,date,positive,allowed \
  --required-columns customer_id,name,email,signup_date,amount \
  --valid-email-columns email \
  --parseable-date-columns signup_date \
  --positive-columns amount \
  --allowed-columns status \
  --allowed-values active,blocked \
  --dedup fuzzy \
  --dedup-columns name,email \
  --fuzzy-threshold 90 \
  --report report.html
```

## API

Rinse exposes a FastAPI adapter over the same pipeline.

```bash
PYTHONPATH=src python3 -m uvicorn rinse.interfaces.api:app --reload
```

Endpoints:

- `POST /api/datasets/upload`
- `GET /api/datasets/{id}/profile`
- `POST /api/datasets/{id}/preview`
- `POST /api/jobs/clean`
- `GET /api/jobs/{id}`
- `GET /api/jobs/{id}/result`
- `GET /api/jobs/{id}/report`
- `GET /api/jobs/{id}/download`
- `GET /api/jobs/{id}/report/download`

The API queues clean jobs on a background executor, stores dataset/job/artifact metadata in local SQLite, and writes uploaded files, clean outputs, and reports to local artifact storage.

The local SQLite and filesystem storage are intentionally simple runtime defaults. Redis, PostgreSQL, and S3/R2 fit behind the same job/storage boundaries when the deployment target needs distributed workers or external artifact storage.

## Web Interface

The Next.js interface lives in `web` and calls the FastAPI adapter directly.

```bash
cd web
npm install
npm run dev
```

By default, the web app expects the API at `http://127.0.0.1:8000`. Set `NEXT_PUBLIC_RINSE_API_URL` when using a different API origin.

The first screen supports:

- file upload or built-in sample data;
- dataset profile and column display;
- operation selection with parameters;
- before/after preview from the API;
- report summary from structured cleaning results;
- clean job status and recent jobs;
- clean file and audit report downloads.

## Reports

Reports are generated from `CleaningReport` data, not console output. JSON reports are machine-readable, and HTML reports are intended for human review.

Report contents include:

- rows before and after cleaning;
- rows removed;
- changed cell counts;
- validation issue counts;
- duplicate group counts;
- detailed cell changes with before and after values;
- validation issues with row, column, rule, value, and message;
- fuzzy duplicate groups with kept rows, matched rows, scores, and reasons;
- type inference suggestions with confidence and explanation;
- export artifacts for clean output and report files.

Generate an HTML report:

```bash
rinse clean tests/fixtures/dirty_customers.csv \
  --out clean.json \
  --validate required \
  --required-columns name,email \
  --report report.html
```

## Cleaning Operations

### Normalization

- Text normalization trims whitespace, collapses repeated spaces, and applies optional casing.
- Email normalization trims and lowercases valid email-like values while reporting invalid values.
- Date normalization converts configured input formats into a target output format.
- Phone normalization uses region-aware formatting and reports invalid phone numbers.

### Deduplication

- Exact deduplication can compare whole rows or selected columns.
- Fuzzy deduplication compares selected columns through RapidFuzz.
- `suggest` mode reports duplicate candidates without deleting rows.
- `remove_strict` mode deletes only matches above the configured threshold.
- Duplicate reports include kept rows, matched rows, scores, and reasons.

### Validation And Data Quality

- Type inference presents suggestions without changing the dataset.
- Missing value handling can keep values, drop rows, fill static values, or use mean, median, or mode where appropriate.
- Validation rules cover required values, ranges, positive numbers, allowed values, email validity, and date parseability.
- Validation failures are reported instead of silently corrected.

## Fixture Dataset

The repository includes realistic messy customer data:

- `tests/fixtures/dirty_realistic_customers.csv`
- `tests/fixtures/dirty_realistic_customers.xlsx`

The fixture includes duplicate and fuzzy-duplicate customers, mixed date formats, invalid emails, inconsistent casing, extra spaces, missing values, a broken date, invalid phone data, and invalid status values.

Golden outputs are checked in:

- `tests/fixtures/expected_realistic_customers_clean.json`
- `tests/fixtures/expected_realistic_customers_report.json`

Example cleaned records:

```json
[
  {
    "customer_id": "C-001",
    "name": "Alice Smith",
    "email": "alice@example.com",
    "signup_date": "2026-01-02",
    "amount": 100.0,
    "status": "active",
    "phone": "+14155552671"
  },
  {
    "customer_id": "C-002",
    "name": "Bob Stone",
    "email": "bad-email",
    "signup_date": "broken",
    "amount": "1",
    "status": "draft",
    "phone": "123"
  }
]
```

## Tests

```bash
python3 -m pytest -q
cd web
npm run build
```

The Python test suite covers architecture boundaries, file adapters, operations, pipeline behavior, golden fixtures, CLI behavior, and API flows. The web build verifies the Next.js interface and TypeScript contracts.

## Homebrew

Install from the repository formula:

```bash
brew install --HEAD ./Formula/rinse.rb
rinse --help
```

For a public tap after release:

```bash
brew tap Hqzdev/rinse
brew install rinse
```

## Current Limitations

- The API uses a local background executor, SQLite metadata, and filesystem artifact storage by default.
- Distributed job queues, PostgreSQL metadata, and object storage are deployment adapter work, not local defaults.
- Fuzzy deduplication should stay in `suggest` mode unless thresholds and comparison columns are chosen carefully.
- PDF report export is intentionally deferred while HTML reports remain the human-readable artifact format.
- Web recent jobs are session-local; a backend list-jobs endpoint is the next step for shared multi-session history.
