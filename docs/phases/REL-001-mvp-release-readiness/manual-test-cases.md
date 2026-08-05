# REL-001 Manual Test Cases: MVP release readiness

## Test inventory

| ID | Title | Priority | Status |
|---|---|---|---|
| `REL-001-TC-01` | Verify lightweight base and optional extras | Critical | Passed locally |
| `REL-001-TC-02` | Missing browser dependency fails actionably | High | Passed by automation |
| `REL-001-TC-03` | Enforce the absolute chunk ceiling | Critical | Passed locally |
| `REL-001-TC-04` | Install wheel cleanly and run golden path | Critical | Passed locally |
| `REL-001-TC-05` | Verify MVP scope, versions, and changelog | High | Passed by automation |
| `REL-001-TC-06` | Complete regression and public checks | Critical | Passed |
| `REL-001-TC-07` | Tag and publish the verified MVP merge | Critical | Ready; pending merge approval |

### [REL-001-TC-01] Base wheel metadata excludes heavy legacy dependencies

- **Requirement IDs:** `REL-001-FR-01`, `REL-001-API-02`, `REL-001-API-03`, `REL-001-AC-01`
- **Component / Module:** Packaging
- **Priority:** Critical
- **Type:** Functional / Regression
- **Preconditions:** Candidate `pyproject.toml` is available.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Inspect base `Requires-Dist` entries. | Playwright, pdf2image, and pytesseract are absent from unconditional dependencies. |
| **2** | Inspect `browser`, `ocr`, and `legacy` extras. | Browser contains Playwright; OCR contains pdf2image/pytesseract; legacy contains both groups. |
| **3** | Install the base wheel in a clean virtual environment. | Universal CLI dependencies install; Playwright remains unavailable. |

- **Postconditions:** Clean environment remains available for TC-04.
- **Test Data:** Built `0.2.0` wheel metadata only.
- **Execution:** Metadata contract passed locally on 2026-08-06.

### [REL-001-TC-02] SPA mode reports the browser extra when unavailable

- **Requirement IDs:** `REL-001-FR-02`, `REL-001-AC-02`
- **Component / Module:** Legacy crawl CLI
- **Priority:** High
- **Type:** Negative / Usability
- **Preconditions:** Playwright is unavailable or simulated as unavailable.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Invoke legacy `crawl URL --spa --no-upload`. | Command returns non-zero before importing the legacy scraper. |
| **2** | Inspect stderr. | Message recommends `pip install 'doc-harvester[browser]'`; no traceback or URL query is printed. |

- **Postconditions:** No crawl or external write occurred.
- **Test Data:** Synthetic `https://example.com` URL; network is not contacted.
- **Execution:** Passed by `tests/test_cli.py` on 2026-08-06.

### [REL-001-TC-03] Long and real-world content respects the absolute chunk ceiling

- **Requirement IDs:** `REL-001-FR-03`, `REL-001-FR-06`, `REL-001-NFR-02`, `REL-001-AC-03`
- **Component / Module:** Structure-aware chunker / Real-site processing
- **Priority:** Critical
- **Type:** Boundary / Integration / Regression
- **Preconditions:** RFC Editor robots policy allows `/rfc/rfc9110.html`; run uses depth 0, limit 1, delay 1, and 10 MB fetch bound.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Chunk synthetic long unpunctuated and numbered normative blocks at max 50. | Every chunk is at most 50 tokens; no oversized/violation count. |
| **2** | Crawl the official RFC 9110 HTML page with the stated bounds. | One allowed HTML resource enters the temporary manifest. |
| **3** | Process with max 800 and inspect only aggregate metrics. | One document, 2,104 blocks, 182 chunks, maximum 800, zero oversized, quality passed. |
| **4** | Inspect Git status. | No raw manifest, content, or dataset was added to Git. |

- **Postconditions:** Raw public-page artifacts remain temporary and uncommitted.
- **Test Data:** Official RFC 9110 HTML plus synthetic repeated technical words.
- **Execution:** Passed locally on 2026-08-06 after the initial run exposed three oversized chunks (maximum 1,454); the fix reduced maximum to 800 and quality failures to zero.

### [REL-001-TC-04] Clean installed wheel completes the MVP smoke

- **Requirement IDs:** `REL-001-FR-04`, `REL-001-API-05`, `REL-001-NFR-01`, `REL-001-AC-04`
- **Component / Module:** Wheel / Console script / CI
- **Priority:** Critical
- **Type:** Packaging / Integration / Release
- **Preconditions:** A fresh virtual environment contains no editable project install.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Build the `0.2.0` wheel and install it into the clean environment. | Installation succeeds using wheel metadata. |
| **2** | Run version and offline demo. | CLI reports `0.2.0`; demo writes valid chunks. |
| **3** | Assert Playwright cannot be imported. | Assertion passes for the base install. |
| **4** | Serve repository golden-path fixtures on loopback and run crawl/process/inspect. | Four resources process successfully through the installed console script. |

- **Postconditions:** Temporary environment and artifacts contain only synthetic data.
- **Test Data:** `examples/golden-path/site`.
- **Execution:** Passed locally in a clean Python 3.11 environment on 2026-08-06; public
  Python 3.12 wheel job remains pending.

### [REL-001-TC-05] MVP scope and release metadata are consistent

- **Requirement IDs:** `REL-001-FR-05`, `REL-001-FR-07`, `REL-001-API-01`, `REL-001-AC-05`
- **Component / Module:** README / Changelog / Package metadata
- **Priority:** High
- **Type:** Documentation / Regression
- **Preconditions:** Candidate documentation is complete.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Compare pyproject, runtime version, README status, and changelog. | Every location identifies version `0.2.0`. |
| **2** | Review `docs/mvp-scope.md`. | Supported outcome, formats, limitations, safety defaults, extras, and release criteria are explicit. |
| **3** | Review changelog release sections. | User-visible capabilities, dependency change, CI, and security controls are summarized. |

- **Postconditions:** Release documentation is ready for public review.
- **Test Data:** Repository text and metadata only.
- **Execution:** Version/metadata automation passed locally on 2026-08-06.

### [REL-001-TC-06] Complete candidate verification passes

- **Requirement IDs:** `REL-001-NFR-03`–`REL-001-NFR-06`, `REL-001-AC-06`
- **Component / Module:** Repository / GitHub Actions / CodeQL
- **Priority:** Critical
- **Type:** Regression / Security / Release
- **Preconditions:** Candidate changes are complete and staged safely.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Run Ruff, focused tests, complete standalone, and DocProc suites. | All pass. |
| **2** | Build/install/smoke the wheel and inspect metadata. | All pass without heavy optional dependencies. |
| **3** | Run diff validation and staged/history secret scans. | No malformed diff or secret appears. |
| **4** | Open the PR and review all required CI/CodeQL jobs, including `wheel`. | Every required check passes and PR is mergeable. |

- **Postconditions:** Candidate may be merged but is not tagged yet.
- **Test Data:** Synthetic repository fixtures and sanitized aggregate evidence.
- **Execution:** Passed locally on 2026-08-06: Ruff, 39 focused tests, 264 standalone tests,
  107 DocProc tests, clean-wheel smoke, real-page smoke, diff/YAML validation, and
  56-commit history scan. PR #23 passed all eight public checks and is mergeable.

### [REL-001-TC-07] Verified merge is tagged and published

- **Requirement IDs:** `REL-001-FR-08`, `REL-001-NFR-06`, `REL-001-AC-07`
- **Component / Module:** Git / GitHub release
- **Priority:** Critical
- **Type:** Release / Operational
- **Preconditions:** Candidate PR is merged; post-merge checks pass; maintainer authorizes release creation.

### STEPS TO REPRODUCE:

| # | Action / Step | Expected Result |
|---|---|---|
| **1** | Verify clean `main`, merge commit, version, and checks. | All reference the accepted `0.2.0` candidate. |
| **2** | Create annotated tag `v0.2.0` at that exact commit and push it. | Remote tag resolves to the verified merge commit. |
| **3** | Create a GitHub release from `v0.2.0` using the changelog summary. | Public release is visible and identifies the CLI-first MVP limitations. |
| **4** | Verify release/tag URLs and repository status. | Release is published once; local `main` stays clean. |

- **Postconditions:** GitHub MVP release exists; PyPI remains unchanged.
- **Test Data:** Verified merge commit and sanitized release notes.
- **Execution:** Pending merge and explicit release authorization.
