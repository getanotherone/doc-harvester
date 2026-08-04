# CLI-001 Manual Test Cases: Credential-free source orchestration

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `CLI-001-TC-01` | Manual source discovery | High | Passed locally |
| `CLI-001-TC-02` | Sitemap source discovery | Critical | Passed by automation |
| `CLI-001-TC-03` | Local source fetch | Critical | Passed locally |
| `CLI-001-TC-04` | HTTP source fetch | High | Passed by automation |
| `CLI-001-TC-05` | Write and configuration safeguards | Critical | Passed by automation |
| `CLI-001-TC-06` | Backward compatibility and complete validation | Critical | In progress |

## Safety and test-data rules

- Use repository files, temporary directories, and a disposable local HTTP server.
- Do not test with tokens, signed URLs, private hosts, or personal documents.
- Never use `--overwrite` on a file that is not disposable.

---

### [CLI-001-TC-01] Manual discovery writes a universal manifest

- **Requirement IDs:** `CLI-001-FR-01`, `CLI-001-FR-03`, `CLI-001-AC-01`
- **Component / Module:** `source discover manual`
- **Priority:** High
- **Type:** Functional, Positive, Regression
- **Preconditions:** Project is installed in the active virtual environment.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run manual discovery with `README.md`, the same path with a fragment, and `docs/architecture.md`, limit `2`. | The command exits zero and emits two ordered, unique resources. |
| **2** | Repeat with `--output /tmp/doc-harvester-manifest.json`. | JSON is written to that file rather than stdout. |
| **3** | Inspect the JSON. | Schema version is `1`; provider is `manual`; count and resource fields are correct. |

- **Postconditions:** One disposable manifest may exist under `/tmp`.
- **Cleanup / Rollback:** Delete the disposable manifest.
- **Test Data:** Public repository Markdown files.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation and local CLI smoke test
- **Actual Result:** Versioned stdout manifest contained two ordered resources; automated file-output and validation cases passed.
- **Evidence:** `tests/test_source_cli.py`; local CLI output
- **Issue:** Not applicable

---

### [CLI-001-TC-02] Sitemap discovery exposes safe traversal controls

- **Requirement IDs:** `CLI-001-FR-02`, `CLI-001-FR-03`, `CLI-001-AC-02`
- **Component / Module:** `source discover sitemap`
- **Priority:** Critical
- **Type:** Functional, Integration, Boundary
- **Preconditions:** A disposable local HTTP server exposes synthetic sitemap XML.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run sitemap discovery against the local sitemap URL with a small positive limit. | A versioned manifest is emitted with same-origin resources. |
| **2** | Repeat with robots disabled and explicit sitemap/XML/timeout bounds. | The supplied values are accepted and discovery remains bounded. |
| **3** | Add `--allow-cross-origin` to a disposable fixture containing an external test-server URL. | The provider accepts HTTP(S) resources from the second local origin. |

- **Postconditions:** No page body is fetched; only sitemap resources are requested.
- **Cleanup / Rollback:** Stop the local servers and remove fixtures.
- **Test Data:** Synthetic sitemap XML and localhost URLs.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Injected provider verified root, limit, sitemap/XML/timeout bounds, robots control, and cross-origin control without external network access.
- **Evidence:** `test_sitemap_discovery_forwards_bounds_and_controls`
- **Issue:** Not applicable

---

### [CLI-001-TC-03] Local fetch writes a selected file and receipt

- **Requirement IDs:** `CLI-001-FR-04`–`CLI-001-FR-07`, `CLI-001-AC-03`
- **Component / Module:** `source fetch`, local-file adapter
- **Priority:** Critical
- **Type:** Functional, Positive, Security
- **Preconditions:** `README.md` exists and the output path is disposable.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Fetch `README.md` with automatic selection, root `.`, and output `/tmp/doc-harvester-readme.md`. | The local-file fetcher is selected and bytes are written. |
| **2** | Inspect stdout JSON. | Receipt has schema `1`, fetcher `local-file`, correct output, media type, filename, and byte count. |
| **3** | Compare the source and output. | Contents are identical. |

- **Postconditions:** A disposable output exists under `/tmp`.
- **Cleanup / Rollback:** Delete the output.
- **Test Data:** Public repository README.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation and local CLI smoke test
- **Actual Result:** Automatic local selection wrote the exact source bytes and emitted the expected receipt; local `cmp` passed.
- **Evidence:** `test_local_fetch_auto_selection_writes_bytes_and_receipt`; local CLI output
- **Issue:** Not applicable

---

### [CLI-001-TC-04] HTTP fetch uses bounded orchestration

- **Requirement IDs:** `CLI-001-FR-04`, `CLI-001-FR-06`, `CLI-001-FR-07`, `CLI-001-AC-03`
- **Component / Module:** `source fetch`, HTTP adapter
- **Priority:** High
- **Type:** Functional, Integration, Boundary
- **Preconditions:** A disposable local HTTP server serves a small text file.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Fetch the localhost HTTP URL with an explicit output, byte limit, and timeout. | The HTTP fetcher is selected, exits zero, and writes exact bytes. |
| **2** | Set the byte limit below the response size and use another output path. | Fetch fails and the destination is not created. |

- **Postconditions:** At most one successful disposable output exists.
- **Cleanup / Rollback:** Stop the server and remove output/fixtures.
- **Test Data:** Small public synthetic text.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Injected HTTP fetch verified automatic selection, timeout/byte options, bytes, and receipt without external network access.
- **Evidence:** `test_http_fetch_auto_selection_passes_limits`, `test_fetch_failure_creates_no_output`
- **Issue:** Not applicable

---

### [CLI-001-TC-05] Existing output and invalid configuration are rejected safely

- **Requirement IDs:** `CLI-001-FR-05`, `CLI-001-API-05`, `CLI-001-NFR-02`, `CLI-001-AC-04`
- **Component / Module:** Source CLI safeguards
- **Priority:** Critical
- **Type:** Negative, Security, Boundary
- **Preconditions:** A disposable output file already contains known marker text.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Fetch to the existing output without `--overwrite`. | Command fails and marker text is unchanged. |
| **2** | Repeat with `--overwrite`. | Command succeeds and atomically replaces the disposable output. |
| **3** | Supply zero/negative limit, byte bound, or timeout. | Argument parsing fails before discovery/fetch work begins. |
| **4** | Select an unsupported automatic URI scheme. | Command fails clearly and creates no output. |

- **Postconditions:** Disposable output may contain fetched test data.
- **Cleanup / Rollback:** Delete it.
- **Test Data:** Marker text and synthetic input.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Existing output was preserved by default, overwrite replaced it without a temporary-file remainder, and invalid bounds/schemes created no output.
- **Evidence:** `tests/test_source_cli.py`
- **Issue:** Not applicable

---

### [CLI-001-TC-06] Legacy commands and complete repository validation remain green

- **Requirement IDs:** `CLI-001-FR-08`, `CLI-001-NFR-04`, `CLI-001-AC-05`
- **Component / Module:** CLI regression, packaging, security
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Development/DocProc dependencies and Gitleaks are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Parse every pre-existing public command with its established arguments. | Parsing remains compatible. |
| **2** | Run Ruff and complete standalone and DocProc suites. | All checks pass. |
| **3** | Build and inspect the wheel and run CLI help/smoke checks. | New command code is packaged and help renders. |
| **4** | Run secret scans and review PR CI/CodeQL. | No leak is found and all required checks pass. |

- **Postconditions:** Only ignored or temporary artifacts exist.
- **Cleanup / Rollback:** Remove disposable build output if desired.
- **Test Data:** Repository source only.

### Execution record

- **Status:** In progress
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Legacy parsing passed; Ruff, 123 standalone tests, 107 DocProc tests,
  wheel contents/import, CLI artifact smoke test, and Gitleaks scans passed. PR CI remains.
- **Evidence:** Local validation output; PR to be assigned
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Source parser and manual manifest | `tests/test_source_cli.py` |
| Sitemap option orchestration | `tests/test_source_cli.py` with injected provider |
| Local/HTTP fetch and write guards | `tests/test_source_cli.py` with temporary files/injected fetcher |
| Legacy command compatibility | `tests/test_cli.py` |
| Full regression and packaging | Local validation and CI |

## Traceability review

- [x] Every requirement and acceptance criterion has a planned test path.
- [x] Positive, negative, boundary, filesystem, and privacy cases are included.
- [x] Remote behavior is reproducible with disposable localhost services.
- [x] Destructive behavior is limited to explicit overwrite of disposable output.
- [ ] Execution records and public evidence will be added after implementation.
