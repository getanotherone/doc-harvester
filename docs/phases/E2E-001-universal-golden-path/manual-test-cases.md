# E2E-001 Manual Test Cases: Credential-free universal golden path

## Test inventory

| ID | Title | Priority | Status |
|---|---|---|---|
| `E2E-001-TC-01` | Run the multi-format loopback pipeline | Critical | Passed by automation |
| `E2E-001-TC-02` | Inspect without source/content disclosure | Critical | Passed by automation |
| `E2E-001-TC-03` | Store the validated dataset locally | High | Passed by automation |
| `E2E-001-TC-04` | Expose quality status and preview publication | Critical | Passed by automation |
| `E2E-001-TC-05` | Preserve checkpoint on restart | Critical | Passed by automation |
| `E2E-001-TC-06` | Complete public walkthrough and regression validation | Critical | Passed |

Use [the golden-path walkthrough](../../golden-path.md) for the copyable manual workflow.
Keep all outputs in a disposable local directory and never substitute production URLs or
documents when collecting public evidence.

### [E2E-001-TC-01] Multi-format loopback content reaches a processed dataset

- **Requirement IDs:** `E2E-001-FR-01`, `E2E-001-FR-02`, `E2E-001-AC-01`
- **Component / Module:** Crawler / Fetchers / Extractors / Processing CLI
- **Priority:** Critical
- **Type:** Functional / Positive / Integration
- **Preconditions:**
  1. Development dependencies are installed in `.venv`.
  2. Only the repository-owned synthetic fixtures are used.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Start the loopback site and crawl it with delay zero and limit 20. | Version-1 manifest contains seven allowed resources; protected route is counted but not fetched. |
| **2** | Process the manifest into a new dataset directory. | All seven HTML/PDF/DOCX/XLSX/XML/text resources are processed without a raw fetch failure. |
| **3** | Inspect `processing-report.json`. | Counts match the manifest and each processed outcome references its required artifacts. |

- **Postconditions:** Manifest and dataset remain available as explicit checkpoints.
- **Test Data:** Synthetic P-100 equipment content; no credentials or real organization data.
- **Execution:** Passed by `tests/test_universal_pipeline_integration.py` on 2026-08-06.

### [E2E-001-TC-02] Default inspection does not disclose content or source URLs

- **Requirement IDs:** `E2E-001-FR-03`, `E2E-001-NFR-04`, `E2E-001-AC-02`
- **Component / Module:** Dataset review
- **Priority:** Critical
- **Type:** Privacy / Regression
- **Preconditions:** TC-01 produced a valid dataset with at least one quality warning.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Run `source inspect DATASET` without URI opt-in. | Receipt declares `source_uris_included: false`. |
| **2** | Review every document entry. | Only safe filename, media type, extractor, counts, statuses, and finding codes appear. |
| **3** | Compare quality counts with the processing receipt. | Every quality-failed document is represented; no failure is hidden. |

- **Postconditions:** Dataset is unchanged.
- **Test Data:** TC-01 dataset.
- **Execution:** Passed by integration assertions on 2026-08-06.

### [E2E-001-TC-03] Validated dataset stores through the local backend

- **Requirement IDs:** `E2E-001-FR-04`, `E2E-001-AC-03`
- **Component / Module:** Dataset storage / Local StorageBackend
- **Priority:** High
- **Type:** Functional / Positive
- **Preconditions:** TC-01 dataset exists; destination root is outside the dataset.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Run `source store` with `--storage local` and explicit root/destination. | Receipt reports local provider and uploaded file/byte totals. |
| **2** | Inspect the destination tree. | `processing-report.json` and all referenced document artifacts exist. |
| **3** | Repeat without `--overwrite`. | Command fails without replacing the stored checkpoint. |

- **Postconditions:** One complete local stored copy remains.
- **Test Data:** Destination `golden-path/run-001` under a disposable root.
- **Execution:** Initial storage passed by integration automation on 2026-08-06.

### [E2E-001-TC-04] Quality warning is visible and publication remains preview-only

- **Requirement IDs:** `E2E-001-FR-05`, `E2E-001-FR-06`, `E2E-001-NFR-03`, `E2E-001-AC-04`
- **Component / Module:** Dataset publication / Local Publisher
- **Priority:** Critical
- **Type:** Safety / Functional / Negative
- **Preconditions:** Select a processed document whose quality status is `warning`.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Render the selected index without including source URI. | Markdown header visibly states `Quality: warning`; source URI is absent. |
| **2** | Run local `publish` without `--apply`. | Receipt reports `would_create`. |
| **3** | Inspect publisher root. | No destination file was created. |

- **Postconditions:** Review Markdown exists locally; publisher destination does not.
- **Test Data:** Processed document index 0 from TC-01.
- **Execution:** Passed by integration assertions on 2026-08-06.

### [E2E-001-TC-05] Restart refuses the existing checkpoint before fetching

- **Requirement IDs:** `E2E-001-FR-07`, `E2E-001-API-03`, `E2E-001-AC-05`
- **Component / Module:** Manifest processing orchestration
- **Priority:** Critical
- **Type:** Negative / Recovery / Regression
- **Preconditions:** TC-01 completed and loopback request/report snapshots were recorded.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Repeat processing with the existing dataset output path. | Command returns non-zero and reports `output already exists`. |
| **2** | Compare loopback request list. | No additional network request occurred. |
| **3** | Compare processing-report bytes. | Existing checkpoint is byte-identical. |

- **Postconditions:** Original dataset remains usable for later stages.
- **Test Data:** TC-01 manifest/dataset.
- **Execution:** Passed by request and byte snapshots on 2026-08-06.

### [E2E-001-TC-06] Walkthrough and complete repository verification pass

- **Requirement IDs:** `E2E-001-FR-08`, `E2E-001-NFR-01`–`E2E-001-NFR-06`, `E2E-001-AC-06`
- **Component / Module:** Documentation / Packaging / Repository CI
- **Priority:** Critical
- **Type:** Manual / Regression / Release
- **Preconditions:** Candidate branch contains the completed E2E phase.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Follow `docs/golden-path.md` from a clean environment. | Local crawl/process/inspect/store/render/preview completes with no credentials. |
| **2** | Run Ruff, focused E2E tests, standalone tests, and DocProc tests. | All checks pass. |
| **3** | Build the wheel and inspect/import it. | Public packages and commands remain available. |
| **4** | Run diff and staged/history secret scans. | No malformed diff or secret is found. |
| **5** | Review PR CI and CodeQL. | All required checks pass before merge. |

- **Postconditions:** Candidate is ready to merge only after public checks pass.
- **Test Data:** Repository synthetic fixtures only.
- **Execution:** Passed locally on 2026-08-06: public walkthrough, Ruff, 87 focused tests,
  261 standalone tests, 107 DocProc tests, wheel build/content inspection, diff validation,
  and 54-commit history scan. PR #22 passed seven checks and merged as `b0e9a05`.
