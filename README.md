# Rinse

Clean messy CSV and Excel files: deduplication, normalization, validation, conversion, and an auditable before/after report.

## Architecture

Rinse starts with a hexagonal core. The data-cleaning engine is isolated from delivery details, so CLI, API, web UI, file storage, and report rendering can change without rewriting domain logic.

```text
src/rinse/
  domain/          core entities and value objects
  application/     use cases that orchestrate ports
  ports/           interfaces for external capabilities
  adapters/        concrete readers, writers, and renderers
  infrastructure/  database, storage, queue, and config details
  interfaces/      CLI, API, and web entrypoints
```

Current boundary rules:

- `domain` does not import FastAPI, Typer, pandas, openpyxl, Redis, or SQLAlchemy.
- `application` depends on ports, not concrete adapters.
- file readers, writers, storage, reports, jobs, CLI, and API sit outside the core.

## File adapters

The first concrete adapters support tabular file IO through the `DatasetReader` and `DatasetWriter` ports:

- CSV read/write through pandas.
- XLSX read/write through pandas with openpyxl.
- JSON record export.
- format detection from `DatasetReference`.
- structured errors for unsupported formats and invalid file references.

## Cleaning pipeline

Cleaning work is orchestrated through a composable pipeline. Each operation receives a `Dataset`, returns a new `Dataset`, and emits an `OperationResult`. The pipeline aggregates those results into a machine-readable `CleaningReport` with row counts, changed cells, validation issues, and duplicate groups.

## First milestone

The MVP path is core first, then CLI and reports, then API and web:

1. Architecture skeleton.
2. CSV/XLSX/JSON readers and writers.
3. Cleaning pipeline and structured report model.
4. Exact and fuzzy deduplication.
5. Normalization operations.
6. CLI and sample datasets.
