# Changelog

## 0.1.1

- Added verified desktop and mobile screenshots to the README.
- Fixed source-checkout CLI commands so they bypass stale global executables.
- Fixed mobile web layout overflow in the live API workflow.
- Added release hygiene documentation for the completed product surface.

## 0.1.0

- Added a hexagonal Python cleaning engine with domain, application, ports, adapters, and interfaces.
- Added CSV, XLSX, and JSON dataset readers and writers.
- Added composable cleaning operations for normalization, deduplication, validation, type inference, and missing values.
- Added JSON and HTML audit report generation from structured `CleaningReport` data.
- Added Typer CLI commands for profiling and cleaning datasets.
- Added FastAPI upload, profile, preview, job, result, report, and download endpoints.
- Added local background job execution with SQLite metadata and filesystem artifact storage.
- Added a Next.js web interface for upload, operation selection, preview, reports, and downloads.
- Added realistic dirty customer fixtures and golden-file tests.
