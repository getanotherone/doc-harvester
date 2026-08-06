# Changelog

All notable changes are documented here. The project follows Semantic Versioning after
the first stable release.

## [Unreleased]

No unreleased changes.

## [0.2.1] - 2026-08-06

### Added

- PyPI project metadata and a release-gated Trusted Publishing workflow that builds,
  validates, smoke-tests, and publishes wheel and source distributions without a stored
  registry token.
- Public PyPI publishing guide, community launch guidance, and structured bug and feature
  request forms for first users and contributors.

### Changed

- Make the standard installation path `pip install doc-harvester`, while retaining a
  documented source checkout for contributors and pre-publication fallback.

## [0.2.0] - 2026-08-06

### Added

- Provider-neutral core contracts and credential-free discovery, crawling, fetching,
  extraction, chunking, enrichment, quality, storage, and publishing adapters.
- Review-gated `source` CLI workflow with versioned manifests and datasets.
- Digital-text PDF, structure-aware DOCX, bounded XLSX, HTML/XML, and text processing.
- Safe local storage, dataset inventory, Markdown rendering, and dry-run-first publication.
- Credential-free golden path covering the complete local workflow.
- Confluence Cloud and Notion publisher adapters plus publisher plugin discovery.
- S3-compatible storage and secure AWS testing guidance.

### Changed

- Playwright and OCR Python libraries are optional `browser`, `ocr`, or `legacy` extras
  instead of default dependencies.
- CI now builds and installs the wheel in a clean environment and runs an installed-package
  golden-path smoke test.
- Upgrade `requests` to 2.33.0 and the pytest stack to pytest 9.0.3.

### Security

- Sanitized public history, repeatable Gitleaks CI, URL redaction, bounded network and file
  processing, robots-aware crawling, and explicit overwrite/apply permissions.

## [0.1.0] - 2026-07-13

### Added

- Fresh sanitized open-source source tree.
- Installable `doc-harvester` package and CLI.
- Offline extraction, chunking, and metadata demo.
- HTML, PDF, DOCX, XLSX, XML, OCR, and token-aware chunking pipeline components.
- FastAPI wrapper and optional DocProc service.
- Project governance, security, and contribution documentation.
