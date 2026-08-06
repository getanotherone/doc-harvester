# Contributing

Thank you for considering a contribution. New contributors are welcome to start with an
issue labeled [`good first issue`](https://github.com/getanotherone/doc-harvester/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22)
or [`help wanted`](https://github.com/getanotherone/doc-harvester/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22help%20wanted%22).
Comment on the issue before beginning substantial work so scope and approach can be
confirmed without wasted effort.

## Development setup

1. Create a Python 3.11 or 3.12 virtual environment.
2. Run `python -m pip install -e '.[dev,api]'`. Add `legacy` only when changing the
   legacy SPA/OCR workflow.
3. Run `ruff check .` and `pytest -q` before submitting a change.
4. Run the DocProc suite separately with
   `PYTHONPATH=services/doc_proc/backend/src pytest -q services/doc_proc/tests`.

## Pull requests

- Keep changes focused and describe behavioral impact.
- Add regression tests for bug fixes and integration tests for pipeline changes.
- Do not commit crawled documents, generated datasets, credentials, local Wiki maps,
  virtual environments, or runtime state.
- Preserve backward compatibility for the flat `src/` modules unless a migration is
  documented.
- Document new environment variables and provider configuration.
- Reference the issue being addressed and describe the user-visible result.

Small documentation fixes, synthetic extractor fixtures, actionable error improvements,
and provider-neutral adapter tests are good first contributions. Contributions must not
include downloaded third-party documents, private URLs, credentials, or personal datasets.

## Phase documentation

For a significant feature or integration phase, add a public task summary and manual test
suite under `docs/phases/<phase-id>-<short-name>/`. Use stable requirement, acceptance,
and test IDs so reviewers can trace each behavior to its verification.

Copy the reusable [task-summary](docs/phases/templates/task-summary.md) and
[manual-test-cases](docs/phases/templates/manual-test-cases.md) templates. Small changes
that do not alter behavior may mark phase documentation as not applicable in the pull
request template, with a short reason.

Commit synthetic examples and sanitized results only. Keep credentials, real remote IDs,
private URLs, raw reports, and customer data local. See
[`docs/phases/README.md`](docs/phases/README.md) for the directory convention, required
content, execution statuses, and public/private boundary.

## Provider contributions

Storage, discovery, and publisher integrations should keep vendor-specific behavior out
of the core pipeline. New providers must include contract tests and must fail with clear
errors when credentials are absent.

## Reporting security issues

Do not open public issues for vulnerabilities or exposed credentials. Follow
[SECURITY.md](SECURITY.md).
