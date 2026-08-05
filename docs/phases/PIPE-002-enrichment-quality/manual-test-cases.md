# PIPE-002 Manual Test Cases: Neutral enrichment and quality gates

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `PIPE-002-TC-01` | Verify neutral metadata enrichment | High | Passed by automation |
| `PIPE-002-TC-02` | Detect poor chunk quality | Critical | Passed by automation |
| `PIPE-002-TC-03` | Keep default quality findings advisory | Critical | Passed by automation |
| `PIPE-002-TC-04` | Enforce quality without losing evidence | Critical | Passed by automation |
| `PIPE-002-TC-05` | Verify public API and configuration | High | Passed |
| `PIPE-002-TC-06` | Complete regression and release validation | Critical | Passed; post-merge pending |

## Safety and test-data rules

- Use synthetic or redistributable local documents.
- Use a new disposable output directory for every run.
- Do not put credentials, private URLs, or source document bodies in execution records.
- Inspect aggregate findings and metadata; do not publish private normalized output.

---

### [PIPE-002-TC-01] Neutral metadata is added to documents and chunks

- **Requirement IDs:** `PIPE-002-FR-01`, `PIPE-002-FR-02`, `PIPE-002-AC-01`
- **Component / Module:** Metadata enrichment and manifest processing
- **Priority:** High
- **Type:** Functional, Positive, Regression
- **Preconditions:** A version-1 manifest references a small synthetic text or structured document.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `doc-harvester source process manifest.json --root . --output /tmp/enriched-dataset`. | Processing completes and publishes the dataset. |
| **2** | Inspect the document metadata. | Enricher, source type, language, document class, counts, hash, and quality status are present. |
| **3** | Inspect chunk metadata. | Each chunk contains neutral source/class/language/hash fields and the document language. |
| **4** | Search the new fields for vendor/domain classifications. | No inferred vendor, organization, electrical type, or product domain is present. |

- **Postconditions:** One disposable dataset exists.
- **Cleanup / Rollback:** Remove only the disposable dataset.
- **Test Data:** Synthetic English, Cyrillic, mixed, or table content.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Neutral metadata and stable normalized hashes were added; tabular structure was classified without domain fields.
- **Evidence:** `tests/test_enrichment_quality.py`; `tests/test_manifest_processing.py`
- **Issue:** Not applicable

---

### [PIPE-002-TC-02] Quality gate reports weak extraction patterns

- **Requirement IDs:** `PIPE-002-FR-03`–`PIPE-002-FR-05`, `PIPE-002-AC-02`
- **Component / Module:** Basic quality gate and quality artifact
- **Priority:** Critical
- **Type:** Functional, Negative, Boundary
- **Preconditions:** Synthetic chunks include empty, tiny, repeated, noisy, and oversized examples.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Evaluate the synthetic document with strict test thresholds. | The quality report fails. |
| **2** | Inspect finding codes. | Codes identify every exceeded empty/tiny/duplicate/noisy/oversized ratio. |
| **3** | Inspect metrics and thresholds. | Counts, ratios, average/maximum tokens, and configured limits are recorded. |
| **4** | Evaluate clean chunks or ratios exactly at their limits. | The report passes when no limit is exceeded. |

- **Postconditions:** No external state changes.
- **Cleanup / Rollback:** None.
- **Test Data:** Synthetic chunk objects only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Stable findings and aggregate metrics covered all five classes; clean input and boundary behavior passed.
- **Evidence:** `tests/test_enrichment_quality.py`
- **Issue:** Not applicable

---

### [PIPE-002-TC-03] Default quality findings remain advisory

- **Requirement IDs:** `PIPE-002-FR-04`–`PIPE-002-FR-06`, `PIPE-002-AC-03`
- **Component / Module:** `source process` default policy
- **Priority:** Critical
- **Type:** Integration, Positive, Regression
- **Preconditions:** A valid manifest produces chunks that fail at least one default threshold.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Process the manifest without `--fail-on-quality`. | Command exits zero if no processing error occurs. |
| **2** | Inspect the CLI summary and processing report. | Failed-quality count is positive and enforcement is false. |
| **3** | Inspect `quality.json`, document, and chunks. | Warning status, findings, and enriched artifacts are retained. |

- **Postconditions:** One reviewable local dataset exists.
- **Cleanup / Rollback:** Remove only that dataset.
- **Test Data:** Short synthetic text/HTML manifest.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Two short resources produced warnings while processing completed and retained all output.
- **Evidence:** `test_process_manifest_extracts_and_chunks_local_text_and_html`; CLI integration tests
- **Issue:** Not applicable

---

### [PIPE-002-TC-04] Enforced quality fails the command but preserves review output

- **Requirement IDs:** `PIPE-002-FR-07`, `PIPE-002-NFR-03`, `PIPE-002-AC-04`
- **Component / Module:** CLI enforcement policy and atomic dataset output
- **Priority:** Critical
- **Type:** Integration, Negative, Recovery
- **Preconditions:** A valid manifest produces a deterministic quality warning and output path is new.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run processing with `--fail-on-quality`. | Command returns non-zero after processing. |
| **2** | Inspect the destination. | Dataset, normalized document, chunks, `quality.json`, and processing report all exist. |
| **3** | Inspect report status and policy fields. | Processing is complete, quality failed count is positive, and enforcement is true. |
| **4** | Fix input/thresholds and rerun to a new output. | A passing run returns zero. |

- **Postconditions:** Failed and passing review datasets may exist.
- **Cleanup / Rollback:** Remove both disposable outputs.
- **Test Data:** Short synthetic document and version-1 manifest.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Enforcement returned `1` while the complete review dataset remained available.
- **Evidence:** `test_source_process_cli_can_enforce_quality_and_preserve_output`
- **Issue:** Not applicable

---

### [PIPE-002-TC-05] Public adapters and settings are available and safe

- **Requirement IDs:** `PIPE-002-FR-08`, `PIPE-002-API-01`–`PIPE-002-API-06`, `PIPE-002-AC-05`
- **Component / Module:** Factories, CLI, environment template, wheel
- **Priority:** High
- **Type:** API, Configuration, Packaging, Negative
- **Preconditions:** Editable or wheel installation is active.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Import/list/create the basic enricher and quality gate. | Public imports and factories return contract implementations. |
| **2** | Run `doc-harvester source process --help`. | All minimum-token, ratio, and enforcement options are visible. |
| **3** | Inspect `.env.example`. | Prefixed safe defaults are present and enforcement defaults to `0`. |
| **4** | Supply minimum tokens `0` or a ratio outside `[0,1]`. | CLI rejects the value before processing. |
| **5** | Inspect and install the wheel. | Both adapter packages import successfully from the installed artifact. |

- **Postconditions:** None outside disposable package-test files.
- **Cleanup / Rollback:** Remove temporary wheel/smoke directories.
- **Test Data:** Repository configuration and synthetic core objects.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Public factories, defaults, environment/CLI precedence, invalid-bound rejection, wheel contents, and isolated installed-wheel smoke passed.
- **Evidence:** `tests/test_enrichment_quality.py`; `tests/test_source_cli.py`; `tests/test_env_example.py`; local wheel validation
- **Issue:** Not applicable

---

### [PIPE-002-TC-06] Complete repository and release validation pass

- **Requirement IDs:** `PIPE-002-NFR-04`, `PIPE-002-NFR-05`, `PIPE-002-AC-06`
- **Component / Module:** Regression, packaging, security, CI
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Standalone and DocProc development dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build/inspect/install the wheel and run enrichment/quality smoke checks. | New packages are present and operational. |
| **3** | Run history/public-tree secret scans. | No leak is found. |
| **4** | Review PR and post-merge CI/CodeQL. | Every required check passes. |

- **Postconditions:** Only ignored or temporary artifacts exist.
- **Cleanup / Rollback:** Remove disposable build/smoke output if desired.
- **Test Data:** Repository and synthetic objects only.

### Execution record

- **Status:** Passed; post-merge pending
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Ruff, 209 standalone tests, 107 DocProc tests, wheel build/contents/import/smoke, diff validation, 40-commit history scan, staged public-tree scan, and PR Python 3.11/3.12, DocProc, secrets, and CodeQL pass; post-merge checks are pending.
- **Evidence:** Local validation output; [PR #16](https://github.com/getanotherone/doc-harvester/pull/16)
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Neutral metadata, hashes, gate findings, thresholds, factories | `tests/test_enrichment_quality.py` |
| Artifact/report output and enforcement retention | `tests/test_manifest_processing.py` |
| CLI/environment policy and precedence | `tests/test_source_cli.py`, `tests/test_env_example.py` |
| Universal contract compatibility | `tests/test_core_contracts.py` |

## Traceability review

Every acceptance criterion maps to a manual case and automated evidence. Final post-merge
results remain to be recorded in `PIPE-002-TC-06`.
