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

## Deduplication

Rinse supports exact deduplication and fuzzy deduplication as pipeline operations:

- exact deduplication can compare complete rows or selected columns.
- fuzzy deduplication compares selected columns through a text similarity scorer.
- `suggest` mode reports risky duplicate candidates without removing rows.
- `remove_strict` mode removes matches only when they meet the configured threshold.
- duplicate groups include the kept row, matched rows, similarity score, and reason.

## Validation

Rinse includes required-value validation as a first standalone validation operation:

- required columns can be checked before or after normalization.
- blank strings and empty spreadsheet cells are reported as validation issues.
- validation issues include row, column, rule, value, and message details in the audit report.

## Normalization

Rinse includes visible normalization operations for common spreadsheet cleanup:

- text normalization trims whitespace, collapses repeated spaces, and can normalize casing.
- email normalization trims, lowercases, and reports invalid emails.
- date normalization converts configured input formats into one output format and reports parse failures.
- phone normalization uses a region-aware formatter and reports invalid phone numbers.

## CLI

Rinse exposes the core pipeline through a terminal interface:

```bash
rinse profile tests/fixtures/dirty_customers.csv
rinse clean tests/fixtures/dirty_customers.csv --out clean.xlsx --normalize text,email --text-columns name --email-columns email
rinse clean tests/fixtures/dirty_customers.csv --out clean.json --validate required --required-columns name,email --report report.json
```

The CLI reads and writes through adapters, converts between supported file formats based on the output extension, and runs the same application pipeline that future API and web interfaces will call.

## Audit reports

The `--report` option writes a machine-readable JSON report:

- row counts before and after cleaning.
- rows removed, cells changed, validation issue count, and duplicate group count.
- detailed cell changes with before/after values.
- detailed validation issues and duplicate groups.

## Homebrew

For local Homebrew installation from the current repository:

```bash
brew install --HEAD ./Formula/rinse.rb
rinse --help
```

For a public tap after the first release:

```bash
brew tap Hqzdev/rinse
brew install rinse
```

## First milestone

The first MVP milestone is complete:

1. Architecture skeleton.
2. CSV/XLSX/JSON readers and writers.
3. Cleaning pipeline and structured report model.
4. Exact and fuzzy deduplication.
5. Normalization operations.
6. CLI and sample datasets.
7. Required-value validation.
8. JSON audit report export.
9. CLI file conversion through output formats.
