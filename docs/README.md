# Documentation

## Project phases

- [P0 — Stabilize](phases/P0-stabilize/task-summary.md)
- [P0 manual test cases](phases/P0-stabilize/manual-test-cases.md)
- [P1 — Sanitize](phases/P1-sanitize/task-summary.md)
- [P1 manual test cases](phases/P1-sanitize/manual-test-cases.md)
- [CORE-001 — Universal core](phases/CORE-001-universal-core/task-summary.md)
- [CORE-001 manual test cases](phases/CORE-001-universal-core/manual-test-cases.md)
- [ADAPT-001 — Credential-free discovery and fetching](phases/ADAPT-001-credential-free-adapters/task-summary.md)
- [ADAPT-001 manual test cases](phases/ADAPT-001-credential-free-adapters/manual-test-cases.md)
- [CLI-001 — Credential-free source orchestration](phases/CLI-001-source-orchestration/task-summary.md)
- [CLI-001 manual test cases](phases/CLI-001-source-orchestration/manual-test-cases.md)
- [PIPE-001 — Manifest-driven local processing](phases/PIPE-001-manifest-processing/task-summary.md)
- [PIPE-001 manual test cases](phases/PIPE-001-manifest-processing/manual-test-cases.md)
- [EXTR-001 — Digital-text PDF extraction](phases/EXTR-001-pdf/task-summary.md)
- [EXTR-001 manual test cases](phases/EXTR-001-pdf/manual-test-cases.md)
- [EXTR-002 — Structure-aware DOCX extraction](phases/EXTR-002-docx/task-summary.md)
- [EXTR-002 manual test cases](phases/EXTR-002-docx/manual-test-cases.md)
- [EXTR-003 — Bounded XLSX extraction](phases/EXTR-003-xlsx/task-summary.md)
- [EXTR-003 manual test cases](phases/EXTR-003-xlsx/manual-test-cases.md)
- [PIPE-002 — Neutral enrichment and quality gates](phases/PIPE-002-enrichment-quality/task-summary.md)
- [PIPE-002 manual test cases](phases/PIPE-002-enrichment-quality/manual-test-cases.md)
- [STORE-001 — Validated dataset storage](phases/STORE-001-dataset-storage/task-summary.md)
- [STORE-001 manual test cases](phases/STORE-001-dataset-storage/manual-test-cases.md)
- [PUB-002 — Reviewed dataset publication](phases/PUB-002-reviewed-dataset-publication/task-summary.md)
- [PUB-002 manual test cases](phases/PUB-002-reviewed-dataset-publication/manual-test-cases.md)
- [REVIEW-001 — Privacy-safe dataset inventory](phases/REVIEW-001-dataset-inventory/task-summary.md)
- [REVIEW-001 manual test cases](phases/REVIEW-001-dataset-inventory/manual-test-cases.md)
- [CRAWL-001 — Safe provider-neutral web crawling](phases/CRAWL-001-safe-web-crawling/task-summary.md)
- [CRAWL-001 manual test cases](phases/CRAWL-001-safe-web-crawling/manual-test-cases.md)
- [E2E-001 — Credential-free universal golden path](phases/E2E-001-universal-golden-path/task-summary.md)
- [E2E-001 manual test cases](phases/E2E-001-universal-golden-path/manual-test-cases.md)

## Operations and security

- [Backup and restore](operations/backup-and-restore.md)
- [Credential rotation](security/credential-rotation.md)
- [Downloaded-document redistribution review](security/redistribution-review.md)

- [Architecture](architecture.md): current components, data flow, and boundaries.
- [Credential-free golden path](golden-path.md): run the complete review-gated workflow
  against repository-owned local fixtures.
- [Configuration](configuration.md): environment variables and safe defaults.
- [Providers](providers.md): storage and publishing extension contracts.
- [Wiki automation](wiki-automation.md): generating and publishing documentation.
- [Notion dry-run](notion-dry-run.md): connect one page and verify access without changing it.
- [S3-compatible test connection](s3-testing.md): start locally, then test a scoped
  Cloudflare R2 bucket with cleanup steps.
- [AWS S3 Free Plan connection](aws-s3-testing.md): secure a new AWS account, configure a
  private bucket and least-privilege test identity, upload a dataset, and clean up.
- [Phase documentation](phases/README.md): public task summaries, manual tests, and
  privacy-safe evidence conventions, including reusable templates.
- [PUB-001 Notion publishing validation](phases/PUB-001-notion-publishing-validation/task-summary.md):
  current requirements, acceptance criteria, outcome, and manual test suite.
- [Legacy scraper reference](scraper_full_documentation.md): detailed behavior of the
  original electrical-engineering profile. This document is retained as an implementation
  reference and may use older command terminology.
