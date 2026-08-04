# EXTR-001 Manual Test Cases: Digital-text PDF extraction

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `EXTR-001-TC-01` | Process a local digital-text PDF | Critical | Passed locally |
| `EXTR-001-TC-02` | Report an image-only PDF as OCR-required | High | Passed by automation |
| `EXTR-001-TC-03` | Reject invalid and over-limit PDFs safely | Critical | Passed by automation |
| `EXTR-001-TC-04` | Verify public adapter and configuration surface | High | Passed by automation |
| `EXTR-001-TC-05` | Complete regression and package validation | Critical | Passed |

## Safety and test-data rules

- Use synthetic PDFs or documents whose redistribution license is known.
- Use only a new disposable output directory, preferably below `/tmp`.
- Do not use confidential PDFs, signed URLs, passwords, or credentials.
- The output intentionally excludes the original PDF bytes.

---

### [EXTR-001-TC-01] Digital-text PDF produces page-aware chunks

- **Requirement IDs:** `EXTR-001-FR-01`–`EXTR-001-FR-04`, `EXTR-001-FR-07`, `EXTR-001-AC-01`
- **Component / Module:** PDF extractor and `source process`
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** A reviewed manifest references a redistribution-safe two-page PDF containing selectable text.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `doc-harvester source process manifest.json --root . --output /tmp/pdf-dataset`. | Command exits zero and creates the new dataset. |
| **2** | Inspect `processing-report.json`. | Resource is `processed` with extractor `pdf` and non-zero block/chunk counts. |
| **3** | Inspect `documents/00000/document.json`. | Blocks contain expected text and one-based page values; metadata reports page counts and `ocr_used: false`. |
| **4** | Inspect `chunks.json`. | Chunks are non-empty, bounded, and retain page-related structure metadata. |
| **5** | List output files. | Only report/document/chunk JSON exists; no original PDF is copied. |

- **Postconditions:** Disposable local dataset exists.
- **Cleanup / Rollback:** Remove only the disposable dataset.
- **Test Data:** Synthetic two-page digital-text PDF and version-1 manual manifest.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation and installed-artifact smoke test
- **Actual Result:** Two pages produced ordered page-aware blocks and chunks; the wheel adapter extracted the expected one-page smoke text and the installed CLI exposed the page bound.
- **Evidence:** `test_pdf_extractor_preserves_page_numbers_and_metadata`; `test_process_manifest_extracts_and_chunks_local_pdf`; local wheel smoke
- **Issue:** Not applicable

---

### [EXTR-001-TC-02] Textless PDF is explicitly marked for OCR

- **Requirement IDs:** `EXTR-001-FR-04`, `EXTR-001-FR-06`, `EXTR-001-AC-02`
- **Component / Module:** PDF extraction outcome handling
- **Priority:** High
- **Type:** Functional, Negative, Compatibility
- **Preconditions:** A synthetic one-page PDF has no embedded text.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process a manifest containing only the textless PDF. | Command returns non-zero because it produced no processable document. |
| **2** | Inspect the report. | Outcome is `skipped`, reason is `ocr_required`, and page count is recorded. |
| **3** | Inspect the output and running environment. | No document directory or source PDF exists; Poppler/Tesseract was not invoked. |

- **Postconditions:** A disposable report-only dataset exists.
- **Cleanup / Rollback:** Remove it.
- **Test Data:** Synthetic textless PDF.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** The textless PDF was skipped with `ocr_required`, page count `1`, no document artifacts, and no OCR execution.
- **Evidence:** `test_process_manifest_reports_image_only_pdf_as_ocr_required`
- **Issue:** Not applicable

---

### [EXTR-001-TC-03] Invalid and over-limit PDFs fail safely

- **Requirement IDs:** `EXTR-001-FR-02`, `EXTR-001-FR-05`, `EXTR-001-NFR-02`, `EXTR-001-AC-03`
- **Component / Module:** PDF parser safeguards
- **Priority:** Critical
- **Type:** Negative, Boundary, Security
- **Preconditions:** Synthetic malformed and two-page PDFs are available.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process content advertised as PDF without a valid signature. | Resource fails safely and no document artifacts are written. |
| **2** | Process a two-page PDF with `--max-pdf-pages 1`. | Resource fails because it exceeds the configured bound. |
| **3** | Use `--max-pdf-pages 0`. | CLI rejects the setting before processing. |

- **Postconditions:** Only safe disposable reports may exist.
- **Cleanup / Rollback:** Remove them.
- **Test Data:** Synthetic malformed and bounded PDFs.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Invalid signatures/parser input and over-limit PDFs failed safely; non-positive CLI bounds were rejected.
- **Evidence:** `tests/test_pdf_extractor.py`; `test_source_process_cli_rejects_non_positive_bounds`
- **Issue:** Not applicable

---

### [EXTR-001-TC-04] Public API and configuration expose PDF support

- **Requirement IDs:** `EXTR-001-API-01`–`EXTR-001-API-05`, `EXTR-001-AC-04`
- **Component / Module:** Extractor factory, CLI, environment template, documentation
- **Priority:** High
- **Type:** API, Configuration, Regression
- **Preconditions:** Editable installation is active.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Import `PDFExtractor`, list extractors, and create `pdf`. | Public imports/factories return the PDF adapter. |
| **2** | Run `doc-harvester source process --help`. | `--max-pdf-pages` is documented. |
| **3** | Inspect `.env.example` and configuration docs. | Universal positive default and OCR limitation are clear. |

- **Postconditions:** None.
- **Cleanup / Rollback:** None.
- **Test Data:** Repository configuration only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Public import/factory selection, environment catalogue coverage, packaged module presence, and installed CLI help all passed.
- **Evidence:** Adapter/configuration tests and local wheel inspection
- **Issue:** Not applicable

---

### [EXTR-001-TC-05] Complete repository and distributable validation pass

- **Requirement IDs:** `EXTR-001-NFR-03`, `EXTR-001-NFR-04`, `EXTR-001-AC-05`
- **Component / Module:** Regression, package, security
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Development and DocProc dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build and inspect the wheel; run an installed-artifact PDF smoke test. | PDF adapter is packaged and the CLI processes the fixture. |
| **3** | Run secret scans and review PR CI/CodeQL. | No leak is found and all required checks pass. |

- **Postconditions:** Only ignored or temporary build artifacts exist.
- **Cleanup / Rollback:** Remove disposable build/smoke output if desired.
- **Test Data:** Repository and synthetic fixture only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Ruff, 160 standalone tests, 107 DocProc tests, wheel build/contents/import/extraction, installed CLI help, diff validation, and both relevant Gitleaks scans passed. PR Python 3.11/3.12, DocProc, secrets, and CodeQL checks passed.
- **Evidence:** Local validation output; [PR #13](https://github.com/getanotherone/doc-harvester/pull/13)
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| PDF extraction, pages, invalid data, limits | `tests/test_pdf_extractor.py` |
| Manifest PDF/scan outcomes | `tests/test_manifest_processing.py` |
| Factories and chunker compatibility | `tests/test_processing_adapters.py` |
| CLI/environment bounds | `tests/test_source_cli.py`, `tests/test_env_example.py` |

## Traceability review

- [x] Each functional/API requirement has a test path.
- [x] Positive, textless, invalid, and boundary cases are covered.
- [x] Test PDFs are synthetic and require no network or external binaries.
- [x] Original document persistence and destructive overwrite remain out of scope.
