# P1 Manual Test Cases

### [P1-TC-01] Complete history and public working tree pass secret scanning

- **Component / Module:** Repository security
- **Priority:** Critical
- **Type:** Security, Regression
- **Preconditions:** Gitleaks is installed; run from the repository root.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `scripts/scan_secrets.sh`. | Complete Git history is scanned with redaction enabled. |
| **2** | Allow the script to build its temporary public-tree snapshot. | Tracked and non-ignored files are scanned; ignored local secrets are not copied. |
| **3** | Check the exit status. | Status is `0` and no secret finding is reported. |

- **Postconditions:** The temporary scan snapshot is deleted by the script.
- **Current status:** Passed on 2026-07-15 with Gitleaks 8.30.1: 9 commits and
  the tracked/non-ignored working tree reported no leaks.

---

### [P1-TC-02] Sensitive URL parts are absent from log-safe values

- **Component / Module:** Security logging helper
- **Priority:** High
- **Type:** Security, Negative, Regression
- **Preconditions:** Test dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `python -m pytest -q tests/test_security.py`. | Tests pass. |
| **2** | Review the test URL containing userinfo, query token, and fragment. | The output retains only scheme, host, and path. |
| **3** | Review the embedded-exception test. | A URL repeated by an exception is sanitized too. |

- **Postconditions:** No external request is sent.
- **Current status:** Passed on 2026-07-15 as part of the 81-test standalone suite.

---

### [P1-TC-03] Credentials are rotated and old values are revoked

- **Component / Module:** External provider security
- **Priority:** Critical
- **Type:** Security, Manual
- **Preconditions:** The operator owns the relevant Yandex, database, storage, Notion, and Confluence accounts.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Inventory credentials using `docs/security/credential-rotation.md`. | Every applicable credential has an owner and rotation status. |
| **2** | Create replacement credentials with least privilege and update local/hosted secret stores. | A safe smoke test succeeds without printing values. |
| **3** | Revoke the old credentials and repeat the smoke test. | New credentials work and old credentials fail. |
| **4** | Record sanitized evidence outside Git. | Evidence includes dates and outcomes, never secret values. |

- **Postconditions:** Old credentials remain revoked.
- **Current status:** Manual gate; not yet confirmed by the credential owner.
