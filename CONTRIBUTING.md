# Contributing

## Development setup

1. Create a Python 3.11 or 3.12 virtual environment.
2. Run `python -m pip install -e '.[dev,api]'`.
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

## Provider contributions

Storage, discovery, and publisher integrations should keep vendor-specific behavior out
of the core pipeline. New providers must include contract tests and must fail with clear
errors when credentials are absent.

## Reporting security issues

Do not open public issues for vulnerabilities or exposed credentials. Follow
[SECURITY.md](SECURITY.md).
