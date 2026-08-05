# REVIEW-001 Manual Test Cases: Privacy-safe dataset inventory

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `REVIEW-001-TC-01` | Inspect a mixed dataset | Critical | Passed by automation |
| `REVIEW-001-TC-02` | Verify privacy defaults and URI opt-in | Critical | Passed by automation |
| `REVIEW-001-TC-03` | Reject invalid and oversized datasets | Critical | Passed by automation |
| `REVIEW-001-TC-04` | Select, render, and preview one document | High | Passed |
| `REVIEW-001-TC-05` | Complete regression and release validation | Critical | Passed |

## Safety and test-data rules

- Use synthetic or already-reviewed local datasets.
- Do not commit redirected inventory output until filenames are reviewed.
- Never use `--include-source-uri` in shared evidence unless every URI is sanitized.
- Inspection is read-only; continue to review rendered Markdown before publication.

---

### [REVIEW-001-TC-01] Mixed dataset produces an actionable inventory

- **Requirement IDs:** `REVIEW-001-FR-01`–`REVIEW-001-FR-04`, `REVIEW-001-FR-07`, `REVIEW-001-AC-01`
- **Component / Module:** Dataset review API and `source inspect`
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** `/tmp/dataset` contains one processed, one skipped, and one failed synthetic outcome.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `doc-harvester source inspect /tmp/dataset`. | Command exits zero and emits version-1 JSON. |
| **2** | Inspect aggregate fields. | Selected/processed/skipped/failed and quality-failed counts equal the dataset. |
| **3** | Inspect the processed entry. | Index, basename, media type, extractor, block/chunk counts, quality status, finding codes/counts, and severity counts are present. |
| **4** | Inspect skipped and failed entries. | Skipped reason/format are safe; failed reason is only `processing_failed`. |

- **Postconditions:** Dataset remains byte-identical.
- **Cleanup / Rollback:** None.
- **Test Data:** Synthetic three-outcome dataset.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Accurate deterministic mixed-outcome inventory was produced.
- **Evidence:** `tests/test_dataset_review.py`

---

### [REVIEW-001-TC-02] Default inventory protects content and source URIs

- **Requirement IDs:** `REVIEW-001-FR-05`, `REVIEW-001-FR-06`, `REVIEW-001-NFR-03`, `REVIEW-001-AC-02`, `REVIEW-001-AC-03`
- **Component / Module:** Inventory privacy policy
- **Priority:** Critical
- **Type:** Security, Privacy, Negative and Positive
- **Preconditions:** Synthetic bodies/errors/messages and token-bearing `example.test` URIs exist.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run normal inspection and search output for bodies, URI token, raw failure, quality message, and private directory. | None appears; basenames and safe codes remain. |
| **2** | Run again with `--include-source-uri` using synthetic data. | Source URI is included for each outcome and the top-level opt-in field is true. |
| **3** | Inspect stderr from an invalid dataset. | Error identifies structure/category without printing private values. |

- **Postconditions:** No source file changes.
- **Cleanup / Rollback:** Discard URI-inclusive output.
- **Test Data:** Fake domains/tokens only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Content, paths, raw errors, messages, and URIs were absent by default; synthetic URI appeared only after opt-in.
- **Evidence:** Privacy and opt-in tests in `tests/test_dataset_review.py`

---

### [REVIEW-001-TC-03] Invalid schemas and configured bounds fail safely

- **Requirement IDs:** `REVIEW-001-FR-01`, `REVIEW-001-FR-08`, `REVIEW-001-NFR-04`, `REVIEW-001-AC-04`
- **Component / Module:** Dataset/artifact validation
- **Priority:** Critical
- **Type:** Negative, Boundary, Security
- **Preconditions:** Disposable malformed dataset variants exist.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Duplicate an outcome index, then use a negative/Boolean index. | Validation returns non-zero with no inventory. |
| **2** | Exceed report, artifact, or outcome-count bound. | Bound is identified without artifact content. |
| **3** | Mismatch chunk count/array or corrupt quality types/findings. | Schema validation fails safely. |
| **4** | Use malformed/wrong-version JSON or unknown status. | Inspection fails without writes. |

- **Postconditions:** No inventory is emitted for rejected data.
- **Cleanup / Rollback:** Remove disposable variants.
- **Test Data:** Synthetic malformed JSON/dataset structures.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Duplicate/negative indexes, artifact/outcome bounds, and chunk-count mismatch were rejected.
- **Evidence:** `tests/test_dataset_review.py`; `tests/test_dataset_storage.py`

---

### [REVIEW-001-TC-04] Inventory selection flows into render and preview

- **Requirement IDs:** `REVIEW-001-API-02`, `REVIEW-001-AC-05`
- **Component / Module:** Inspect, render, and Publisher handoff
- **Priority:** High
- **Type:** End-to-end, Functional, Positive
- **Preconditions:** Reviewed local dataset and disposable output/publisher root exist.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Inspect dataset and choose a processed entry with acceptable quality. | A non-negative index and supporting review fields are available. |
| **2** | Run `source render DATASET --document-index N --output /tmp/review.md`. | Selected content renders; no source URI appears by default. |
| **3** | Inspect Markdown, then run local `publish` without `--apply`. | Status is `would_create` or `would_update`; no destination changes. |

- **Postconditions:** One unpublished Markdown review artifact may remain.
- **Cleanup / Rollback:** Remove disposable `/tmp` outputs.
- **Test Data:** Earlier synthetic/local reviewed dataset.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Local CLI smoke
- **Actual Result:** Inventory selected README index `0` with passed quality; render succeeded without source URI and local preview returned `would_create`.
- **Evidence:** Sanitized local command output; automated render/publisher compatibility tests

---

### [REVIEW-001-TC-05] Complete repository and release validation pass

- **Requirement IDs:** `REVIEW-001-NFR-05`, `REVIEW-001-AC-06`
- **Component / Module:** Regression, packaging, security, CI
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Standalone and DocProc development dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build/inspect wheel and execute installed/extracted-wheel inspect smoke. | New module and command are packaged and operational. |
| **3** | Scan complete history and staged public tree. | No leak is found. |
| **4** | Review PR and post-merge CI/CodeQL. | Every required check passes. |

- **Postconditions:** Working tree contains only intended changes.
- **Cleanup / Rollback:** Remove temporary wheel/smoke artifacts.
- **Test Data:** Repository and reviewed local dataset only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Ruff, 43 focused tests, 240 standalone tests, 107 DocProc tests, wheel build/contents, seven PR checks, post-merge inspection, and 52-commit history scan passed.
- **Evidence:** Local verification output; [PR #20](https://github.com/getanotherone/doc-harvester/pull/20); merge `334f3fa`

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Inventory fields, privacy, bounds, schema, CLI | `tests/test_dataset_review.py` |
| Unique/non-negative outcome indexes | `tests/test_dataset_storage.py` |
| CLI defaults and configuration catalogue | `tests/test_source_cli.py`, `tests/test_env_example.py` |
| Render/publish compatibility | `tests/test_dataset_publication.py`, `tests/test_cli.py` |

## Traceability review

Every acceptance criterion maps to a manual case and automated evidence. Full release counts
and public CI evidence will be recorded after verification.
