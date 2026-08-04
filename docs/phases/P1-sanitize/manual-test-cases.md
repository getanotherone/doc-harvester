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
- **Current status:** Passed again on 2026-08-04: complete history and the
  tracked/non-ignored working tree reported no leaks.

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
- **Current status:** Passed again on 2026-08-04 as part of the 81-test standalone suite.

---

### [P1-TC-03] Credentials receive an approved secure disposition

- **Component / Module:** External provider security
- **Priority:** Critical
- **Type:** Security, Manual
- **Preconditions:** The operator owns the relevant Yandex, database, storage, Notion, and Confluence accounts.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Inventory credentials using `docs/security/credential-rotation.md`. | Every applicable integration is classified as active, rotated, retired, or not configured. |
| **2** | For active integrations, confirm the credential is current and least-scope; for retired integrations, record the owner-approved retirement control. | No obsolete integration remains intentionally usable. |
| **3** | Inspect only environment-variable names and populated/empty state. | No credential value, fingerprint, or private destination is printed. |
| **4** | Record sanitized evidence. | Evidence includes date, provider, disposition, and outcome, never secret values. |

- **Postconditions:** Retired integrations require new credentials before reactivation;
  current credentials remain local and ignored by Git.
- **Current status:** Passed on 2026-08-04. The owner classified Yandex as permanently
  retired with a blocked account, retained the newly created Notion test token, and confirmed
  that Confluence, S3/AWS, database, and custom CI credentials are not configured. The local
  HTTP API setting is the documented placeholder.
