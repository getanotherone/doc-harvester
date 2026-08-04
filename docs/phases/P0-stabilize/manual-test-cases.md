# P0 Manual Test Cases

### [P0-TC-01] Canonical repository structure is unique

- **Component / Module:** Repository structure
- **Priority:** High
- **Type:** Regression, Structural
- **Preconditions:** Run from the repository root.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `find . -name .git -type d -prune`. | Only `./.git` is printed. |
| **2** | Inspect `src/`, `src/doc_harvester/`, and `services/doc_proc/`. | Standalone, public package, and DocProc code use the canonical paths documented in the task summary. |
| **3** | Search for `03_DocProc` and a second DocProc source tree. | No competing implementation is found. |

- **Postconditions:** Repository is unchanged.
- **Current status:** Passed on 2026-07-15.

---

### [P0-TC-02] Complete automated validation passes

- **Component / Module:** Standalone and DocProc test suites
- **Priority:** Critical
- **Type:** Functional, Regression
- **Preconditions:** Development dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `python -m ruff check .`. | No lint errors are reported. |
| **2** | Run `python -m pytest -q`. | Standalone tests pass, including the offline demo contract. |
| **3** | Run `PYTHONPATH=services/doc_proc/backend/src python -m pytest -q services/doc_proc/tests`. | DocProc tests pass, including the XLSX integration contract. |

- **Postconditions:** Test-generated temporary files are removed automatically.
- **Current status:** Passed on 2026-07-15: Ruff passed, 81 standalone tests passed,
  and 107 DocProc tests passed.

---

### [P0-TC-03] Repository backup can be restored

- **Component / Module:** Disaster recovery
- **Priority:** Critical
- **Type:** Recovery, Manual
- **Preconditions:** The operator controls external encrypted storage with sufficient space.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Follow the repository backup procedure in `docs/operations/backup-and-restore.md`. | Git bundle verification succeeds and a temporary clone can read `HEAD`. |
| **2** | Clone the bundle into a temporary location and inspect its latest commit. | The restored repository opens successfully and contains the expected commit. |
| **3** | Record sanitized evidence. | Date, backup medium/category, bundle verification, restore outcome, and commit ID are recorded without tokens or private URLs. |

- **Postconditions:** Temporary restore copies may be removed after evidence is recorded.
- **Current status:** Passed on 2026-07-16. Bundle verification reported complete history;
  the restored repository was clean at `d4d5089`, and required files were present.

---

### [P0-TC-04] Retired Yandex Disk data is excluded from recovery scope

- **Component / Module:** Disaster recovery scope
- **Priority:** Medium
- **Type:** Recovery decision, Manual
- **Preconditions:** The data owner has confirmed that the historical Yandex Disk data will
  not be used again.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Review the current recovery requirements with the data owner. | The owner confirms that future recovery does not depend on Yandex Disk data. |
| **2** | Record the decision without including private folder names or URLs. | P0 identifies the data as intentionally retired rather than accidentally omitted. |

- **Postconditions:** No Yandex Disk data is copied, modified, or deleted by this test.
- **Current status:** Passed on 2026-07-16 by owner decision.
