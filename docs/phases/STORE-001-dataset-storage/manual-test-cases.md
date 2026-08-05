# STORE-001 Manual Test Cases: Validated dataset storage

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `STORE-001-TC-01` | Store a valid dataset locally | Critical | Passed by automation |
| `STORE-001-TC-02` | Reject unsafe or incomplete datasets | Critical | Passed by automation |
| `STORE-001-TC-03` | Protect an existing destination | Critical | Passed by automation |
| `STORE-001-TC-04` | Verify public CLI and configuration | High | Passed by automation |
| `STORE-001-TC-05` | Exercise S3-compatible adapter contract | High | Passed by automation |
| `STORE-001-TC-06` | Complete regression and release validation | Critical | Passed; post-merge pending |

## Safety and test-data rules

- Use only a synthetic or already-reviewed version-1 dataset.
- Run the local case before any remote-provider case.
- Use a unique `manual-test/run-NNN` destination for every non-overwrite run.
- Never put access keys on the command line or in screenshots/evidence.
- For remote testing, use a bucket-scoped token and delete the test prefix afterward.

---

### [STORE-001-TC-01] Valid dataset is stored locally

- **Requirement IDs:** `STORE-001-FR-01`, `STORE-001-FR-02`, `STORE-001-FR-04`, `STORE-001-FR-07`, `STORE-001-AC-01`
- **Component / Module:** Dataset validator, local backend, `source store`
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** A reviewed version-1 dataset exists under `/tmp/dataset`; `/tmp/storage` is disposable.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `doc-harvester source store /tmp/dataset --storage local --local-root /tmp/storage --destination manual-test/run-001`. | Command exits zero. |
| **2** | Inspect the JSON summary. | Provider is `local`; destination, file count, and byte count are present. |
| **3** | Inspect `/tmp/storage/manual-test/run-001`. | Processing report and every referenced document/chunk/quality file exist. |
| **4** | Compare source and stored file counts/content. | Public non-hidden files match; no source file changed. |

- **Postconditions:** One disposable stored copy exists.
- **Cleanup / Rollback:** Remove `/tmp/storage` only.
- **Test Data:** Synthetic one-document processed dataset.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Four expected files were validated and copied with accurate provider/destination/count evidence.
- **Evidence:** `tests/test_dataset_storage.py`
- **Issue:** Not applicable

---

### [STORE-001-TC-02] Unsafe or incomplete dataset is rejected before writes

- **Requirement IDs:** `STORE-001-FR-01`–`STORE-001-FR-03`, `STORE-001-NFR-04`, `STORE-001-AC-02`
- **Component / Module:** Validation and filesystem safety
- **Priority:** Critical
- **Type:** Negative, Security, Boundary
- **Preconditions:** Disposable malformed dataset variants are available.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Remove `quality.json` from a processed outcome and run storage. | Validation fails and target remains empty. |
| **2** | Change an outcome directory to `../outside`. | Unsafe directory is rejected. |
| **3** | Add a nested symlink or use a symlink as dataset root. | Storage is rejected without following the link. |
| **4** | Place the local target inside the source or the source inside the target. | Overlapping trees are rejected. |
| **5** | Use empty or traversal-based destination. | Destination is rejected before backend writes. |
| **6** | Exceed the report-byte bound. | Report is rejected before JSON parsing/backend writes. |

- **Postconditions:** No target artifacts exist.
- **Cleanup / Rollback:** Remove malformed disposable inputs.
- **Test Data:** Synthetic malformed reports/directories/symlinks.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Missing artifacts, unsafe paths, invalid destinations, overlapping local trees, and root/nested symlinks were rejected before writes.
- **Evidence:** `tests/test_dataset_storage.py`; `tests/test_storage.py`
- **Issue:** Not applicable

---

### [STORE-001-TC-03] Default no-overwrite policy preflights every conflict

- **Requirement IDs:** `STORE-001-FR-05`, `STORE-001-FR-06`, `STORE-001-NFR-04`, `STORE-001-AC-03`
- **Component / Module:** `StorageBackend.upload_tree`, CLI policy
- **Priority:** Critical
- **Type:** Negative, Regression, Data safety
- **Preconditions:** The last target file already exists; earlier target files do not.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `source store` without `--overwrite`. | Command returns non-zero and identifies a conflict. |
| **2** | Inspect the existing object. | Its original content remains unchanged. |
| **3** | Inspect earlier would-be target paths. | No partial new files were written. |
| **4** | Repeat intentionally with `--overwrite`. | All files are stored/replaced and command exits zero. |

- **Postconditions:** Existing destination remains unchanged after the default case.
- **Cleanup / Rollback:** Remove only disposable test storage.
- **Test Data:** Two-file source tree and one late conflict.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Full preflight found the late conflict before the first write; explicit overwrite remains available.
- **Evidence:** `test_upload_tree_preflights_all_conflicts_before_writing`; CLI conflict test
- **Issue:** Not applicable

---

### [STORE-001-TC-04] Public command and canonical configuration are exposed

- **Requirement IDs:** `STORE-001-API-01`, `STORE-001-API-02`, `STORE-001-API-05`, `STORE-001-API-06`, `STORE-001-AC-04`
- **Component / Module:** Public module, CLI, `.env.example`, wheel
- **Priority:** High
- **Type:** API, Configuration, Packaging
- **Preconditions:** Editable or wheel installation is active.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Import `validate_dataset` and `store_dataset`. | Public functions import from the installed package. |
| **2** | Run `doc-harvester source store --help`. | Dataset/destination, provider, report bound, overwrite, local, and S3 options appear. |
| **3** | Inspect `.env.example`. | Safe local defaults, prefixed S3 fields, blank credentials/session token are present. |
| **4** | Configure both prefixed and legacy bucket names in a fake environment. | Prefixed canonical value wins. |

- **Postconditions:** None.
- **Cleanup / Rollback:** None.
- **Test Data:** Repository configuration only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Parser, public configuration catalogue, defaults, canonical precedence, wheel contents, and isolated installed CLI smoke pass.
- **Evidence:** Source CLI, environment, storage tests, and local wheel validation
- **Issue:** Not applicable

---

### [STORE-001-TC-05] S3-compatible contract supports scoped and temporary credentials

- **Requirement IDs:** `STORE-001-FR-08`, `STORE-001-API-04`, `STORE-001-AC-05`
- **Component / Module:** S3 adapter and factory
- **Priority:** High
- **Type:** Integration contract, Security, Positive
- **Preconditions:** Fake in-memory S3 client is available; no real credential is used.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Build S3 storage with bucket, prefix, endpoint, region, access/secret/session values. | SDK client receives all connection fields. |
| **2** | Upload a file below a provider prefix. | Expected bucket/key contains the bytes. |
| **3** | Check an absent and present key. | `exists` maps not-found safely and reports present objects. |
| **4** | Inspect outputs/errors. | No credential value is printed. |

- **Postconditions:** In-memory objects only.
- **Cleanup / Rollback:** None.
- **Test Data:** Fake credentials and two-byte JSON file.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Prefix routing, object operations, not-found mapping, and temporary session-token propagation passed without network access.
- **Evidence:** `tests/test_storage.py`
- **Issue:** Not applicable

---

### [STORE-001-TC-06] Complete repository and release validation pass

- **Requirement IDs:** `STORE-001-NFR-05`, `STORE-001-NFR-06`, `STORE-001-AC-06`
- **Component / Module:** Regression, packaging, security, CI
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Standalone and DocProc test dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build/inspect/install the wheel and run local dataset storage smoke. | Module/command are packaged and operational. |
| **3** | Run complete-history and staged-public-tree secret scans. | No leak is found. |
| **4** | Review PR and post-merge CI/CodeQL. | Every required check passes. |

- **Postconditions:** Only ignored or temporary artifacts exist.
- **Cleanup / Rollback:** Remove temporary package/storage directories.
- **Test Data:** Repository and synthetic version-1 dataset only.

### Execution record

- **Status:** Passed; post-merge pending
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Ruff, 54 focused tests, 226 standalone tests, 107 DocProc tests, wheel build/contents, installed discover/process/store smoke, diff validation, 43-commit history scan, staged public-tree scan, and PR Python 3.11/3.12, DocProc, secrets, and CodeQL pass; post-merge checks are pending.
- **Evidence:** Local validation output; [PR #17](https://github.com/getanotherone/doc-harvester/pull/17)
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Dataset/report/artifact/path validation and CLI integration | `tests/test_dataset_storage.py` |
| Tree safety, conflict preflight, S3 adapter/factory | `tests/test_storage.py` |
| Parser and non-secret S3 overrides | `tests/test_source_cli.py` |
| Safe/canonical environment catalogue | `tests/test_env_example.py` |
| Universal backend contract and legacy CLI compatibility | `tests/test_core_contracts.py`, `tests/test_cli.py` |

## Traceability review

Every acceptance criterion maps to a manual case and automated evidence. Final post-merge
results remain to be recorded in `STORE-001-TC-06`.
