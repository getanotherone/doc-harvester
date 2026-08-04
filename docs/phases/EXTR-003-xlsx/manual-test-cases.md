# EXTR-003 Manual Test Cases: Bounded XLSX extraction

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `EXTR-003-TC-01` | Process a typed/formula XLSX workbook | Critical | Passed locally |
| `EXTR-003-TC-02` | Enforce hidden-sheet privacy policy | Critical | Passed by automation |
| `EXTR-003-TC-03` | Reject malformed and over-limit workbooks | Critical | Passed by automation |
| `EXTR-003-TC-04` | Verify public API and configuration | High | Passed by automation |
| `EXTR-003-TC-05` | Complete regression and package validation | Critical | Passed |

## Safety and test-data rules

- Prefer synthetic XLSX files or workbooks with known redistribution permission.
- Do not use confidential hidden sheets, external-link credentials, or macro-enabled files.
- Use a new disposable output directory under `/tmp`.
- Confirm normalized JSON excludes the original workbook.

---

### [EXTR-003-TC-01] Typed workbook produces sheet-aware table chunks

- **Requirement IDs:** `EXTR-003-FR-01`–`EXTR-003-FR-05`, `EXTR-003-FR-09`, `EXTR-003-FR-10`, `EXTR-003-AC-01`
- **Component / Module:** XLSX extractor and `source process`
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** A version-1 manifest references a synthetic workbook with strings, formula, Boolean, date, and pipe text.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `doc-harvester source process manifest.json --root . --output /tmp/xlsx-dataset`. | Command exits zero and publishes the new dataset. |
| **2** | Inspect `processing-report.json`. | Resource is processed with extractor `xlsx` and non-zero block/chunk counts. |
| **3** | Inspect `document.json`. | Rows remain ordered; values are deterministic; pipes are escaped; formula text is retained. |
| **4** | Inspect metadata. | Sheet/row/cell/block/formula counts are correct and `formulas_evaluated` is false. |
| **5** | Inspect chunks/output files. | Sheet section and table type survive, pages are null, and no source XLSX is copied. |

- **Postconditions:** One disposable local dataset exists.
- **Cleanup / Rollback:** Remove only that dataset.
- **Test Data:** Synthetic typed/formula XLSX.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation and installed-wheel smoke test
- **Actual Result:** Typed rows produced deterministic sheet-scoped table blocks/chunks; formula text remained intact and unevaluated; no source workbook was copied. The installed wheel extracted and chunked the expected smoke row.
- **Evidence:** `test_xlsx_extractor_preserves_sheets_rows_values_and_formulas`; `test_process_manifest_extracts_and_chunks_local_xlsx`; local wheel smoke
- **Issue:** Not applicable

---

### [EXTR-003-TC-02] Hidden worksheets require explicit opt-in

- **Requirement IDs:** `EXTR-003-FR-06`, `EXTR-003-FR-07`, `EXTR-003-NFR-03`, `EXTR-003-AC-02`
- **Component / Module:** XLSX privacy policy
- **Priority:** Critical
- **Type:** Security, Privacy, Functional
- **Preconditions:** Workbook contains visible, hidden, and very-hidden worksheets.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process with default settings. | Only visible-sheet rows are extracted. |
| **2** | Inspect metadata and output. | Skipped-hidden count is `2`; hidden titles/content do not appear. |
| **3** | Process a disposable copy with `--include-hidden-xlsx-sheets`. | Hidden and very-hidden rows are included with state metadata. |
| **4** | Repeat with `--no-include-hidden-xlsx-sheets`. | Safe exclusion is restored explicitly. |

- **Postconditions:** Two disposable comparison datasets may exist.
- **Cleanup / Rollback:** Remove both.
- **Test Data:** Synthetic workbook with three sheet states.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Default processing included only visible content and retained only skipped count; explicit adapter, manifest, CLI, and environment opt-in/override paths passed.
- **Evidence:** `test_xlsx_extractor_excludes_hidden_sheets_by_default_and_allows_opt_in`; `test_process_manifest_xlsx_hidden_sheet_policy_is_explicit`; source CLI tests
- **Issue:** Not applicable

---

### [EXTR-003-TC-03] Malformed and over-limit XLSX inputs fail safely

- **Requirement IDs:** `EXTR-003-FR-08`, `EXTR-003-NFR-02`, `EXTR-003-NFR-04`, `EXTR-003-AC-03`
- **Component / Module:** XLSX ZIP/dimension/stream safeguards
- **Priority:** Critical
- **Type:** Negative, Security, Boundary
- **Preconditions:** Synthetic corrupt, incomplete, multi-sheet, multi-row/cell workbooks are available.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process non-ZIP, corrupt ZIP, or missing-workbook OOXML input. | Resource fails safely with no document artifacts. |
| **2** | Exceed entry or expanded-byte limit. | File is rejected before workbook parsing. |
| **3** | Exceed declared/streamed sheet, row, or cell limit. | Processing stops at the configured bound. |
| **4** | Supply zero for any public XLSX numeric bound. | CLI rejects the setting before processing. |

- **Postconditions:** Only disposable report output may exist.
- **Cleanup / Rollback:** Remove it.
- **Test Data:** Synthetic invalid and boundary workbooks.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Signature, ZIP, required-part, entry, expanded-byte, sheet, row, cell, declared-dimension, and non-positive CLI cases failed safely.
- **Evidence:** `tests/test_xlsx_extractor.py`; `test_source_process_cli_rejects_non_positive_bounds`
- **Issue:** Not applicable

---

### [EXTR-003-TC-04] Public adapter and configuration expose XLSX support

- **Requirement IDs:** `EXTR-003-API-01`–`EXTR-003-API-06`, `EXTR-003-AC-04`
- **Component / Module:** Factory, CLI, environment template, documentation
- **Priority:** High
- **Type:** API, Configuration, Regression
- **Preconditions:** Editable installation is active.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Import `XLSXExtractor`, list extractors, and create `xlsx`. | Public surfaces return the XLSX adapter. |
| **2** | Run `doc-harvester source process --help`. | Sheet/row/cell/expanded-byte and hidden-sheet options appear. |
| **3** | Inspect `.env.example` and configuration docs. | Safe positive defaults and hidden inclusion `0` are documented. |

- **Postconditions:** None.
- **Cleanup / Rollback:** None.
- **Test Data:** Repository configuration only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Public imports/factories, environment catalogue and safe default, packaged module, and all installed CLI options passed.
- **Evidence:** Adapter/configuration tests and local wheel inspection
- **Issue:** Not applicable

---

### [EXTR-003-TC-05] Complete repository and distributable validation pass

- **Requirement IDs:** `EXTR-003-NFR-05`, `EXTR-003-NFR-06`, `EXTR-003-AC-05`
- **Component / Module:** Regression, packaging, security
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Development and DocProc test dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build/inspect the wheel and run installed extraction/chunking smoke. | XLSX module is packaged and processes the fixture. |
| **3** | Run history/public-tree secret scans and review PR/post-merge CI/CodeQL. | No leak is found and all checks pass. |

- **Postconditions:** Only ignored or temporary artifacts exist.
- **Cleanup / Rollback:** Remove disposable build/smoke output if desired.
- **Test Data:** Repository and synthetic workbook only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Ruff, 187 standalone tests, 107 DocProc tests, wheel build/contents/import/extraction/chunking, installed CLI help, diff validation, and history/public-tree secret scans passed. PR Python 3.11/3.12, DocProc, secrets, and CodeQL checks passed.
- **Evidence:** Local validation output; [PR #15](https://github.com/getanotherone/doc-harvester/pull/15)
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| XLSX types, formulas, privacy, and safeguards | `tests/test_xlsx_extractor.py` |
| Manifest dataset processing | `tests/test_manifest_processing.py` |
| Factories and structure-aware chunks | `tests/test_processing_adapters.py` |
| CLI/environment validation | `tests/test_source_cli.py`, `tests/test_env_example.py` |

## Traceability review

- [x] Every functional/API requirement has a test path.
- [x] Positive, privacy, malformed, dimension, archive, and configuration cases are covered.
- [x] Fixtures are synthetic and require no network or spreadsheet application.
- [x] Formula execution, original persistence, and destructive overwrite remain excluded.
