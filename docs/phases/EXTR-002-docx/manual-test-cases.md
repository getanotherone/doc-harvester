# EXTR-002 Manual Test Cases: Structure-aware DOCX extraction

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `EXTR-002-TC-01` | Process a structured DOCX | Critical | Passed locally |
| `EXTR-002-TC-02` | Preserve structure through chunking | High | Passed by automation |
| `EXTR-002-TC-03` | Reject unsafe or over-limit containers | Critical | Passed by automation |
| `EXTR-002-TC-04` | Verify public API and configuration | High | Passed by automation |
| `EXTR-002-TC-05` | Complete regression and package validation | Critical | Passed locally; CI pending |

## Safety and test-data rules

- Prefer synthetic DOCX files or documents with a known redistribution license.
- Use only a new disposable output directory, preferably under `/tmp`.
- Do not use confidential documents, signed URLs, macros, or passwords.
- Confirm output contains normalized JSON only, never the source DOCX.

---

### [EXTR-002-TC-01] Structured DOCX produces reviewable blocks and chunks

- **Requirement IDs:** `EXTR-002-FR-01`–`EXTR-002-FR-06`, `EXTR-002-FR-09`, `EXTR-002-AC-01`
- **Component / Module:** DOCX extractor and `source process`
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** A version-1 manifest references a synthetic DOCX containing a heading, paragraph, list item, and two-row table.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `doc-harvester source process manifest.json --root . --output /tmp/docx-dataset`. | Command exits zero and publishes the new dataset. |
| **2** | Inspect `processing-report.json`. | Resource is processed with extractor `docx` and non-zero block/chunk counts. |
| **3** | Inspect `document.json`. | Heading, text, list, and table blocks appear in source order with structural counts. |
| **4** | Inspect `chunks.json`. | Text is non-empty and bounded; section/table metadata is retained. |
| **5** | List output files. | Only report/document/chunk JSON exists; the DOCX is not copied. |

- **Postconditions:** One disposable dataset exists.
- **Cleanup / Rollback:** Remove only that dataset.
- **Test Data:** Synthetic structured DOCX.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation and installed-wheel smoke test
- **Actual Result:** The structured fixture produced ordered heading/text/list/table blocks, normalized chunks, structural counts, and no copied source. The installed wheel extracted the expected smoke text.
- **Evidence:** `test_docx_extractor_preserves_headings_lists_tables_and_sections`; `test_process_manifest_extracts_and_chunks_local_docx`; local wheel smoke
- **Issue:** Not applicable

---

### [EXTR-002-TC-02] DOCX structure survives chunking without fake pages

- **Requirement IDs:** `EXTR-002-FR-03`–`EXTR-002-FR-05`, `EXTR-002-AC-02`
- **Component / Module:** DOCX extractor and structure-aware chunker boundary
- **Priority:** High
- **Type:** Functional, Regression
- **Preconditions:** Structured synthetic DOCX fixture is loaded through the public adapter.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Extract and chunk the fixture with a positive token bound. | At least one chunk is produced. |
| **2** | Inspect chunk section and block types. | Heading-derived section and table type are retained. |
| **3** | Inspect page/start/end page fields. | Values are `null`, because DOCX pagination was not rendered. |

- **Postconditions:** None outside disposable test data.
- **Cleanup / Rollback:** Remove fixtures if persisted.
- **Test Data:** Synthetic DOCX with `Heading1` and table.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Heading-derived section and explicit table type survived chunking; page metadata remained null.
- **Evidence:** `test_docx_extractor_preserves_headings_lists_tables_and_sections`
- **Issue:** Not applicable

---

### [EXTR-002-TC-03] Unsafe and over-limit DOCX containers fail safely

- **Requirement IDs:** `EXTR-002-FR-07`, `EXTR-002-FR-08`, `EXTR-002-NFR-02`, `EXTR-002-NFR-03`, `EXTR-002-AC-03`
- **Component / Module:** OOXML/ZIP validation
- **Priority:** Critical
- **Type:** Negative, Security, Boundary
- **Preconditions:** Synthetic corrupt, incomplete, entity-bearing, and bounded archives are available.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process non-ZIP or incomplete OOXML content advertised as DOCX. | Resource fails safely; no document directory is written. |
| **2** | Process XML containing DTD/entity declarations. | File is rejected before XML parsing. |
| **3** | Exceed the configured archive entry, expanded-byte, XML-byte, or block bound. | Extraction stops with the corresponding safe bound failure. |
| **4** | Supply zero for either public DOCX CLI bound. | CLI rejects the argument before processing. |

- **Postconditions:** Only disposable report output may exist.
- **Cleanup / Rollback:** Remove it.
- **Test Data:** Synthetic invalid/boundary containers.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Signature, ZIP, required-part, DTD/entity, entry, expanded-byte, XML-byte, block, and non-positive CLI cases failed safely.
- **Evidence:** `tests/test_docx_extractor.py`; `test_source_process_cli_rejects_non_positive_bounds`
- **Issue:** Not applicable

---

### [EXTR-002-TC-04] Public adapter and configuration expose DOCX support

- **Requirement IDs:** `EXTR-002-API-01`–`EXTR-002-API-06`, `EXTR-002-AC-04`
- **Component / Module:** Factory, CLI, environment template, documentation
- **Priority:** High
- **Type:** API, Configuration, Regression
- **Preconditions:** Editable installation is active.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Import `DOCXExtractor`, list extractors, and create `docx`. | Public surfaces return the DOCX adapter. |
| **2** | Run `doc-harvester source process --help`. | Both DOCX safety options are documented. |
| **3** | Inspect `.env.example` and configuration docs. | Matching safe positive defaults and scope limitations are present. |

- **Postconditions:** None.
- **Cleanup / Rollback:** None.
- **Test Data:** Repository configuration only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Public import/factory selection, environment catalogue coverage, packaged module presence, and installed CLI options passed.
- **Evidence:** Adapter/configuration tests and local wheel inspection
- **Issue:** Not applicable

---

### [EXTR-002-TC-05] Complete repository and distributable validation pass

- **Requirement IDs:** `EXTR-002-NFR-04`, `EXTR-002-NFR-05`, `EXTR-002-AC-05`
- **Component / Module:** Regression, package, security
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Development and DocProc test dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build/inspect the wheel and run an installed-adapter extraction smoke. | DOCX module is packaged and extracts the fixture. |
| **3** | Run history/public-tree secret scans and review PR/post-merge CI/CodeQL. | No leak is found and all required checks pass. |

- **Postconditions:** Only ignored or temporary artifacts exist.
- **Cleanup / Rollback:** Remove disposable build/smoke output if desired.
- **Test Data:** Repository and synthetic fixture only.

### Execution record

- **Status:** Passed locally; CI pending
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Ruff, 172 standalone tests, 107 DocProc tests, wheel build/contents/import/extraction, installed CLI help, diff validation, and history/public-tree secret scans passed.
- **Evidence:** Local validation output; pull-request evidence pending
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| DOCX structure and safeguards | `tests/test_docx_extractor.py` |
| Manifest processing and dataset output | `tests/test_manifest_processing.py` |
| Factories/chunker compatibility | `tests/test_processing_adapters.py` |
| CLI/environment validation | `tests/test_source_cli.py`, `tests/test_env_example.py` |

## Traceability review

- [x] Every functional/API requirement has a test path.
- [x] Positive, malformed, XML-security, archive-bound, and configuration cases are covered.
- [x] Fixtures are synthetic and require no network, Office software, or new dependency.
- [x] Original-file persistence and destructive overwrite remain excluded.
