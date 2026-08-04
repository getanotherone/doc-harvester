# CORE-001 Manual Test Cases: Universal core contracts

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `CORE-001-TC-01` | Public core API imports | Critical | Passed locally |
| `CORE-001-TC-02` | Provider-neutral pipeline composition | Critical | Passed locally |
| `CORE-001-TC-03` | Core import boundary excludes providers | Critical | Passed locally |
| `CORE-001-TC-04` | Storage and publisher compatibility | High | Passed locally |
| `CORE-001-TC-05` | Complete validation and distributable package | Critical | In progress |

## Safety and test-data rules

- Tests use only synthetic `memory://` and local temporary resources.
- No provider account, credential, private URL, or network request is required.
- Test output must not include local `.env` contents or ignored runtime artifacts.

---

### [CORE-001-TC-01] Public core API imports

- **Requirement IDs:** `CORE-001-FR-01`, `CORE-001-API-01`, `CORE-001-AC-01`
- **Component / Module:** `doc_harvester.core`
- **Priority:** Critical
- **Severity:** Critical
- **Type:** Functional, Positive, Regression
- **Automation Status:** Automated
- **Environment:** Python 3.11 and CI Python 3.11/3.12
- **Current Status:** Passed locally
- **Preconditions:** The project is installed in the active virtual environment.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Import all nine contracts from `doc_harvester.core`. | Import succeeds without credentials or optional provider SDKs. |
| **2** | Import the shared request, artifact, block, chunk, quality, storage, and publish models. | Every documented model is available from the same package. |

- **Postconditions:** No external state changes.
- **Cleanup / Rollback:** Not applicable.
- **Test Data:** Public class names only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** `core-import-ok`; focused tests passed.
- **Evidence:** `tests/test_core_contracts.py`
- **Issue:** Not applicable

---

### [CORE-001-TC-02] Provider-neutral pipeline composition

- **Requirement IDs:** `CORE-001-FR-02`–`CORE-001-FR-06`, `CORE-001-AC-02`
- **Component / Module:** Core pipeline contracts
- **Priority:** Critical
- **Severity:** High
- **Type:** Functional, Integration, Regression
- **Automation Status:** Automated
- **Environment:** Local and CI; no network
- **Current Status:** Passed locally
- **Preconditions:** Test dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `python -m pytest -q tests/test_core_contracts.py`. | Synthetic discovery, crawl, fetch, extraction, chunking, enrichment, and quality stages compose successfully. |
| **2** | Inspect the synthetic output assertions. | Two chunks are produced, metadata is enriched, and the quality gate passes. |

- **Postconditions:** No files or remote resources are created.
- **Cleanup / Rollback:** Pytest removes temporary data.
- **Test Data:** `memory://example.txt`, text `alpha` and `beta`.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Focused core/storage/publisher group reported 16 passed.
- **Evidence:** `test_universal_contracts_compose_without_provider_dependencies`
- **Issue:** Not applicable

---

### [CORE-001-TC-03] Core import boundary excludes providers

- **Requirement IDs:** `CORE-001-NFR-01`, `CORE-001-NFR-02`, `CORE-001-AC-03`
- **Component / Module:** Core package boundary
- **Priority:** Critical
- **Severity:** Critical
- **Type:** Architecture, Security, Regression
- **Automation Status:** Automated
- **Environment:** Local and CI
- **Current Status:** Passed locally
- **Preconditions:** Repository source is available.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Parse imports in every `src/doc_harvester/core/*.py` file. | No Yandex, Notion, Confluence, or other provider adapter module is imported. |
| **2** | Import `doc_harvester.core` without provider credentials. | Import succeeds and performs no network request. |

- **Postconditions:** Repository is unchanged.
- **Cleanup / Rollback:** Not applicable.
- **Test Data:** Core Python source.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Provider-specific import assertions passed.
- **Evidence:** `test_core_package_has_no_provider_specific_imports`
- **Issue:** Not applicable

---

### [CORE-001-TC-04] Storage and publisher compatibility

- **Requirement IDs:** `CORE-001-FR-07`–`CORE-001-FR-09`, `CORE-001-API-04`,
  `CORE-001-API-05`, `CORE-001-AC-04`
- **Component / Module:** Storage and publisher compatibility bridges
- **Priority:** High
- **Severity:** High
- **Type:** Functional, Regression
- **Automation Status:** Automated
- **Environment:** Local and CI
- **Current Status:** Passed locally
- **Preconditions:** Test dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Instantiate local storage and local publisher adapters. | Both instantiate with no provider credential. |
| **2** | Check their universal contract types. | Local storage implements `StorageBackend`; local publisher implements the core `Publisher`. |
| **3** | Run existing storage and publisher tests. | Existing upload, path safety, dry-run, update, and provider adapter behavior remains unchanged. |

- **Postconditions:** Only pytest temporary files are written.
- **Cleanup / Rollback:** Pytest removes temporary data.
- **Test Data:** Synthetic local files and fake provider sessions.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Core/storage/publisher group reported 16 passed.
- **Evidence:** `test_existing_storage_and_publisher_adapters_use_core_contracts`
- **Issue:** Not applicable

---

### [CORE-001-TC-05] Complete validation and distributable package

- **Requirement IDs:** `CORE-001-NFR-03`, `CORE-001-NFR-04`, `CORE-001-AC-06`
- **Component / Module:** Repository validation and packaging
- **Priority:** Critical
- **Severity:** Critical
- **Type:** Regression, Packaging, Security
- **Automation Status:** Automated and CI
- **Environment:** Local Python 3.11; CI Python 3.11/3.12
- **Current Status:** In progress
- **Preconditions:** Development dependencies and Gitleaks are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and the complete standalone test suite. | Lint passes and all standalone tests pass. |
| **2** | Run the complete DocProc test suite. | All DocProc tests pass. |
| **3** | Build a wheel and inspect its file list. | `doc_harvester/core/__init__.py`, `contracts.py`, and `models.py` are present. |
| **4** | Run `scripts/scan_secrets.sh`. | Complete-history and public-tree scans report no leaks. |
| **5** | Review the pull-request checks. | Standalone 3.11/3.12, DocProc, secrets, and CodeQL pass. |

- **Postconditions:** Build/test artifacts remain ignored or are written under `/tmp`.
- **Cleanup / Rollback:** Temporary build output may be removed after inspection.
- **Test Data:** Repository source only.

### Execution record

- **Status:** In progress
- **Executed:** Pending
- **Tester:** Automation
- **Actual Result:** Focused checks passed; complete validation pending.
- **Evidence:** Pending CI
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Public API and composition | `tests/test_core_contracts.py` |
| Boundary validation | `test_core_validates_portable_policy_boundaries` |
| Provider-neutral imports | `test_core_package_has_no_provider_specific_imports` |
| Compatibility | `tests/test_storage.py`, `tests/test_publishers.py` |
| Complete regression | CI `standalone`, `docproc`, `secrets`, and CodeQL jobs |

## Traceability review

- [x] Every functional, API, and non-functional requirement has test or review coverage.
- [x] Every acceptance criterion links to at least one manual or automated test.
- [x] Negative, permission, boundary, recovery, and observability cases were considered.
- [x] Destructive cases define disposable data and cleanup.
- [x] Shared evidence is sanitized.
