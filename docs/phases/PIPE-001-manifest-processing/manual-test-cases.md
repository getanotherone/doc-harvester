# PIPE-001 Manual Test Cases: Manifest-driven local processing

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `PIPE-001-TC-01` | Process local text and HTML manifest | Critical | Passed locally |
| `PIPE-001-TC-02` | Mixed processed, skipped, and failed resources | High | Passed by automation |
| `PIPE-001-TC-03` | Manifest/output/configuration safeguards | Critical | Passed by automation |
| `PIPE-001-TC-04` | Structure-aware chunk bound | High | Passed by automation |
| `PIPE-001-TC-05` | Complete regression and package validation | Critical | In progress |

## Safety and test-data rules

- Use public repository files, synthetic fixtures, `/tmp`, and injected HTTP responses.
- Do not use signed URLs, private documents, credentials, or an existing valued directory.
- The command intentionally refuses to replace its output directory.

---

### [PIPE-001-TC-01] Local manifest produces reviewable documents and chunks

- **Requirement IDs:** `PIPE-001-FR-01`–`PIPE-001-FR-06`, `PIPE-001-AC-01`
- **Component / Module:** `source process`, text/HTML extractors and chunker
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** A version-1 manual manifest references disposable Markdown and HTML fixtures.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `source process` with the manifest, local root, and a new `/tmp` output. | Command exits zero and publishes the output directory. |
| **2** | Inspect `processing-report.json`. | Both resources are `processed`; counts and relative artifact paths are correct. |
| **3** | Inspect each `document.json`. | Resource, extractor, media type, filename, and normalized blocks are present. |
| **4** | Inspect each `chunks.json`. | Chunks have stable indices, non-empty text, token counts, and structure metadata. |

- **Postconditions:** One disposable dataset directory exists.
- **Cleanup / Rollback:** Remove only the disposable `/tmp` directory.
- **Test Data:** Synthetic Markdown and HTML.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation and local CLI smoke test
- **Actual Result:** Two local resources produced document/chunk artifacts, a complete report, and 20 chunks in the documented layout.
- **Evidence:** `test_process_manifest_writes_local_text_and_html_dataset`; local `/tmp` smoke output
- **Issue:** Not applicable

---

### [PIPE-001-TC-02] Mixed manifest preserves every outcome

- **Requirement IDs:** `PIPE-001-FR-03`, `PIPE-001-FR-07`, `PIPE-001-AC-02`
- **Component / Module:** Processing orchestration/report
- **Priority:** High
- **Type:** Integration, Negative, Recovery
- **Preconditions:** Manifest includes supported content, an unsupported PDF, and a failing injected HTTP resource.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process the mixed manifest. | Command returns non-zero because one resource failed. |
| **2** | Inspect the published report. | Supported resource is processed, PDF is skipped as unsupported, and HTTP failure is failed with a safe message. |
| **3** | Inspect the processed document directory. | Successful chunks remain available despite the other outcomes. |

- **Postconditions:** A mixed-result disposable dataset exists.
- **Cleanup / Rollback:** Remove it.
- **Test Data:** Synthetic content and fake failure.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** One processed, one unsupported/skipped, and one safe failed outcome were preserved in a partial report with successful chunks intact.
- **Evidence:** `test_process_manifest_preserves_mixed_outcomes`
- **Issue:** Not applicable

---

### [PIPE-001-TC-03] Invalid input never publishes partial output

- **Requirement IDs:** `PIPE-001-FR-01`, `PIPE-001-FR-02`, `PIPE-001-FR-08`, `PIPE-001-AC-03`
- **Component / Module:** Manifest validation and atomic output
- **Priority:** Critical
- **Type:** Negative, Security, Boundary
- **Preconditions:** Use disposable paths only.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process malformed JSON, wrong schema, mismatched count, and invalid resource entries. | Each command fails before output publication. |
| **2** | Supply an existing output directory. | Command fails without changing it. |
| **3** | Supply zero/negative resource, byte, timeout, or token bounds. | Argument parsing fails before processing. |

- **Postconditions:** Existing marker data is unchanged; no staging directories remain.
- **Cleanup / Rollback:** Remove disposable fixtures.
- **Test Data:** Synthetic invalid manifests and marker directory.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Schema, count, object, metadata, byte, output-exists, and non-positive-bound cases failed without partial publication or marker changes.
- **Evidence:** `tests/test_manifest_processing.py`
- **Issue:** Not applicable

---

### [PIPE-001-TC-04] Structure-aware chunks respect the configured bound

- **Requirement IDs:** `PIPE-001-FR-05`, `PIPE-001-NFR-02`, `PIPE-001-AC-04`
- **Component / Module:** Structure-aware chunker
- **Priority:** High
- **Type:** Functional, Boundary, Regression
- **Preconditions:** Synthetic long paragraphs, table rows, and normative clauses are available.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process with a small positive `--max-tokens`. | Normal content splits into indexed chunks at or below the maximum. |
| **2** | Inspect table/normative content. | Structure metadata is preserved; unavoidable protected oversized structures are explicitly marked. |

- **Postconditions:** Only disposable JSON output exists.
- **Cleanup / Rollback:** Remove it.
- **Test Data:** Synthetic technical paragraphs/table/normative text.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Chunks were indexed and non-empty; all were within the configured bound or explicitly marked oversized.
- **Evidence:** `test_structure_aware_chunker_returns_indexed_bounded_chunks`
- **Issue:** Not applicable

---

### [PIPE-001-TC-05] Complete repository and distributable validation pass

- **Requirement IDs:** `PIPE-001-NFR-04`, `PIPE-001-NFR-05`, `PIPE-001-AC-05`
- **Component / Module:** Regression, package, security
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Development/DocProc dependencies and Gitleaks are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build/inspect the wheel and execute an artifact CLI smoke test. | Extractor/chunker packages and processing command are present and runnable. |
| **3** | Run secret scans and review PR CI/CodeQL. | No leak is found and all required checks pass. |

- **Postconditions:** Only ignored or temporary artifacts exist.
- **Cleanup / Rollback:** Remove disposable build output if desired.
- **Test Data:** Repository source only.

### Execution record

- **Status:** In progress
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Ruff, 151 standalone tests, 107 DocProc tests, wheel contents/import,
  artifact CLI processing smoke, and both Gitleaks scans passed. PR checks remain.
- **Evidence:** Local validation output; PR to be assigned
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Extractor and chunker contracts | `tests/test_processing_adapters.py` |
| Manifest validation/orchestration/output | `tests/test_manifest_processing.py` |
| CLI compatibility | `tests/test_cli.py`, `tests/test_source_cli.py` |
| Full regression/package/security | Local validation and CI |

## Traceability review

- [x] Every requirement and acceptance criterion has a planned test path.
- [x] Positive, mixed-result, unsupported, failure, boundary, and atomicity cases are included.
- [x] Network behavior can be tested through injected fetchers without external access.
- [x] Destructive overwrite is not part of the command.
- [ ] Execution records and public evidence will be added after implementation.
