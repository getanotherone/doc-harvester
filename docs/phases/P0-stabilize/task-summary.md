# P0 — Stabilize

## Summary

Phase 0 establishes one recoverable, testable repository layout before further
architecture work. Repository-side stabilization is complete; backup evidence remains an
operator gate because backups outside this repository cannot be proved by source code.

## Background

The project previously had competing layouts, duplicate processing-service locations, and
an in-progress migration. Continuing without choosing canonical locations would multiply
maintenance and make later provider-neutral work unsafe.

## User story / use case

As a maintainer, I can restore the repository and source data, find one canonical
implementation for each service, and run contract tests that describe the current pipeline.

## System constraints

- Standalone Python code lives in `src/`; the public package lives in `src/doc_harvester/`.
- The canonical document-processing service is `services/doc_proc/`.
- Only the repository root may contain `.git` metadata.
- Backups must be stored outside the repository and must not contain exposed credentials.

## Functional requirements

- `P0-FR-01`: Create and verify a recoverable Git backup.
- `P0-FR-02`: Back up required source data, or explicitly record that obsolete source data
  is intentionally retired and will not be used for recovery.
- `P0-FR-03`: Preserve or deliberately isolate uncommitted migration work.
- `P0-FR-04`: Maintain one canonical scraper and DocProc layout.
- `P0-FR-05`: Run the standalone and DocProc test suites.
- `P0-FR-06`: Preserve integration tests for the standalone demo and DocProc pipeline.

## API requirements

No new external API is introduced. Existing command and pipeline contracts must remain
covered by tests.

## Non-functional requirements

- Recovery instructions must be executable by another maintainer.
- Backup verification must include a restore test, not only file creation.
- Test runs must be reproducible from a clean environment.

## Logging and monitoring

Keep sanitized backup evidence outside Git: date, operator, backup location, verification
result, and a restore-test result. Never record credentials or private download URLs.

## Edge cases

- A Git bundle does not contain uncommitted files.
- A synced cloud folder is not a backup if deletions propagate to it.
- A backup that has never been restored is not considered verified.
- Tests requiring network credentials must remain separate from offline contract tests.

## Acceptance criteria

- One canonical layout and no nested repository are present.
- All repository and DocProc tests pass.
- Integration contracts exist for the current pipeline.
- A maintainer records successful repository backup/restore evidence using the
  [backup runbook](../../operations/backup-and-restore.md).
- Yandex Disk data is either backed up or explicitly classified as retired and unnecessary
  for future recovery.

## Current evidence (2026-07-15)

| Requirement | Status | Evidence |
|---|---|---|
| Canonical layouts | Passed | `src/`, `src/doc_harvester/`, and `services/doc_proc/` are the active locations. |
| No nested repository | Passed | Repository audit found only the root `.git`. |
| Integration contracts | Passed | `tests/test_cli.py` and `services/doc_proc/tests/test_pipeline/test_integration.py`. |
| Complete current test run | Passed | Ruff passed; 81 standalone and 107 DocProc tests passed on 2026-07-15. |
| Repository backup and restore | Manual gate | Evidence must refer to an external backup location. |
| Yandex Disk backup and restore | Not required | The owner confirmed on 2026-07-16 that this data is retired and will never be used again. |
