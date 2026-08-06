# DIST-001 Manual Test Cases: PyPI distribution and community launch

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `DIST-001-TC-01` | Validate distribution metadata and versions | Critical | Passed locally |
| `DIST-001-TC-02` | Verify publishing gates and token-free authentication | Critical | Passed locally |
| `DIST-001-TC-03` | Build and clean-install release artifacts | Critical | Passed locally |
| `DIST-001-TC-04` | Review first-user and contributor paths | High | Passed locally |
| `DIST-001-TC-05` | Publish and install `0.2.1` from PyPI | Critical | Blocked pending account setup and merge |

## Safety and test-data rules

- Use only the embedded demo and synthetic repository fixtures.
- Do not add PyPI tokens; Trusted Publishing is required.
- Publishing is externally visible and must use the authorized `0.2.1` release only.
- If a distribution reaches PyPI, never attempt to overwrite it.

---

### [DIST-001-TC-01] Distribution metadata and versions are valid

- **Requirement IDs:** `DIST-001-FR-01`, `DIST-001-API-01`–`03`, `DIST-001-AC-01`
- **Component / Module:** Packaging metadata
- **Priority:** Critical
- **Severity:** High
- **Type:** Functional / Regression
- **Automation Status:** Automated
- **Environment:** Local and GitHub Actions, Python 3.11/3.12
- **Current Status:** Passed locally
- **Preconditions:** Candidate source tree is available.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run the packaging tests. | Package/runtime versions are `0.2.1`; license, links, extras, and dependencies satisfy contracts. |
| **2** | Build wheel and source distributions and run `twine check`. | Both artifacts build and metadata validation passes. |

- **Postconditions:** Local artifacts exist only under ignored `dist/`.
- **Cleanup / Rollback:** Remove local build artifacts if desired.
- **Test Data:** Public project metadata.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-06
- **Tester:** Codex local validation
- **Actual Result:** Packaging contract passed; wheel and source distribution built; both
  passed Twine metadata validation with version, license expression, and all project URLs.
- **Evidence:** Wheel SHA-256 `94f1c25ccecdd45c8a0b174d559d559e508aae8faa75ff7251ec19f71dda1e5e`;
  source SHA-256 `8cab68c5ce31efd16e89845d702f3bf009a41150ebe399291ce27bac1f90f430`.
- **Issue:** Not applicable

---

### [DIST-001-TC-02] Publishing is gated and uses no stored registry token

- **Requirement IDs:** `DIST-001-FR-02`–`04`, `DIST-001-NFR-02`–`03`, `DIST-001-AC-02`
- **Component / Module:** `.github/workflows/release.yml`
- **Priority:** Critical
- **Severity:** Critical
- **Type:** Security / Negative / Release
- **Automation Status:** Partially automated
- **Environment:** Local workflow review and GitHub Actions
- **Current Status:** Passed locally
- **Preconditions:** Release workflow and packaging tests are available.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Inspect the trigger and permissions. | Only a published release triggers it; build has read access and only publish has `id-token: write`. |
| **2** | Inspect build/publish dependency. | Publish requires successful build, metadata validation, smoke test, and artifact handoff. |
| **3** | Search for PyPI passwords/tokens. | No password, API token, or secret reference exists. |
| **4** | Evaluate a mismatched release tag. | Version assertion fails before building or publishing. |

- **Postconditions:** No release is created and no registry write occurs during local review.
- **Cleanup / Rollback:** Not applicable.
- **Test Data:** Synthetic mismatched tag such as `v9.9.9`.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-06
- **Tester:** Codex local validation
- **Actual Result:** Workflow contract test and YAML parsing passed; release trigger,
  protected environment, build dependency, OIDC permission, and absence of token/password
  configuration were confirmed.
- **Evidence:** `tests/test_packaging.py` and local YAML parse.
- **Issue:** Not applicable

---

### [DIST-001-TC-03] Release artifacts install cleanly and run the demo

- **Requirement IDs:** `DIST-001-FR-03`, `DIST-001-NFR-01`, `DIST-001-AC-03`
- **Component / Module:** Wheel and source distribution
- **Priority:** Critical
- **Severity:** High
- **Type:** Integration / Release / Regression
- **Automation Status:** Automated
- **Environment:** Clean temporary Python 3.11+ virtual environment
- **Current Status:** Passed locally
- **Preconditions:** Valid distributions have been built.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Install only the built wheel into a clean virtual environment. | Installation succeeds without an editable source tree. |
| **2** | Run `doc-harvester --version`. | Output reports `0.2.1`. |
| **3** | Run the credential-free demo to a temporary path. | Command succeeds and writes valid synthetic chunk JSON. |

- **Postconditions:** Temporary environment contains the candidate wheel installation.
- **Cleanup / Rollback:** Delete the temporary environment and demo output.
- **Test Data:** Embedded synthetic HTML demo.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-06
- **Tester:** Codex local validation
- **Actual Result:** Clean Python 3.11 environment installed the wheel with public
  dependencies, reported `doc-harvester 0.2.1`, and wrote one demo chunk successfully.
- **Evidence:** Temporary clean environment `/tmp/doc-harvester-pypi.8n3pCB` (local only).
- **Issue:** Not applicable

---

### [DIST-001-TC-04] First-user and contribution paths are safe and discoverable

- **Requirement IDs:** `DIST-001-FR-05`–`06`, `DIST-001-NFR-04`, `DIST-001-AC-04`
- **Component / Module:** README, contributing guide, issue forms, operator docs
- **Priority:** High
- **Severity:** Medium
- **Type:** Usability / Security / Documentation
- **Automation Status:** Partially automated
- **Environment:** Rendered GitHub repository
- **Current Status:** Passed locally
- **Preconditions:** Documentation and issue forms are present on the candidate branch.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Follow the README quick start. | PyPI install, version, and offline demo commands are concise and source fallback is linked. |
| **2** | Open a new bug or feature issue. | Structured forms request reproducible context and warn against sensitive material. |
| **3** | Follow contributor and community links. | Starter labels, suitable task shapes, privacy rules, and feedback targets are clear. |
| **4** | Review the PyPI operator guide. | Account setup, exact trust fields, release hold points, verification, and rollback are explicit. |

- **Postconditions:** No issue must be submitted during the review.
- **Cleanup / Rollback:** Close an accidental draft without submission.
- **Test Data:** Synthetic bug/feature descriptions.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-06
- **Tester:** Codex local validation
- **Actual Result:** README, contribution guide, operator/community documentation, and all
  three issue chooser YAML files were reviewed and parsed successfully.
- **Evidence:** Local documentation review and YAML parse.
- **Issue:** Not applicable

---

### [DIST-001-TC-05] Authorized `0.2.1` release is installable from PyPI

- **Requirement IDs:** `DIST-001-FR-02`–`06`, `DIST-001-AC-05`
- **Component / Module:** GitHub Releases / PyPI / pip
- **Priority:** Critical
- **Severity:** Critical
- **Type:** Release / Positive / Recovery
- **Automation Status:** Partially automated
- **Environment:** Public GitHub and PyPI; clean local virtual environment
- **Current Status:** Blocked pending account setup and merge
- **Preconditions:** PR is merged with green checks; exact Trusted Publisher and protected `pypi` environment are configured; maintainer authorizes publication.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Publish GitHub release `v0.2.1`. | Release workflow starts against that exact tag. |
| **2** | Review build job and approve the `pypi` deployment. | Build, validation, and smoke pass before an OIDC publication is authorized. |
| **3** | Inspect the PyPI project. | Version `0.2.1`, wheel, source distribution, and verified project links are visible. |
| **4** | Install `doc-harvester==0.2.1` into a clean environment and run version/demo. | Installation succeeds; version and credential-free demo succeed. |

- **Postconditions:** Public immutable `0.2.1` distribution exists.
- **Cleanup / Rollback:** If unsafe, yank rather than overwrite; publish a corrected patch version.
- **Test Data:** Embedded synthetic demo only.

### Execution record

- **Status:** Blocked
- **Executed:** Not run
- **Tester:** Not run
- **Actual Result:** Awaiting account/environment setup and merged release workflow.
- **Evidence:** Not run
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Metadata, version, links, extras | `tests/test_packaging.py::test_release_version_and_optional_heavy_dependencies_are_configured` |
| Release trigger, environment, OIDC, and no token | `tests/test_packaging.py::test_pypi_release_workflow_is_gated_and_uses_trusted_publishing` |
| Build, metadata, clean install, version, demo | `.github/workflows/release.yml` build job and CI wheel job |
| Issue form syntax | Repository YAML validation / rendered GitHub issue chooser |

## Traceability review

- [x] Every functional, API, and non-functional requirement has test or review coverage.
- [x] Every acceptance criterion links to at least one manual or automated test.
- [x] Negative, permission, boundary, recovery, and observability cases were considered.
- [x] Destructive cases define disposable data and cleanup.
- [x] Shared evidence is sanitized.
