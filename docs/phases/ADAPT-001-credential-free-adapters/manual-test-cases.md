# ADAPT-001 Manual Test Cases: Credential-free adapters

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `ADAPT-001-TC-01` | Manual discovery | High | Passed locally |
| `ADAPT-001-TC-02` | Sitemap and robots discovery | Critical | Passed locally |
| `ADAPT-001-TC-03` | Malformed and unsafe sitemap handling | Critical | Passed locally |
| `ADAPT-001-TC-04` | Bounded HTTP fetching | Critical | Passed locally |
| `ADAPT-001-TC-05` | Root-confined local fetching | Critical | Passed locally |
| `ADAPT-001-TC-06` | Factories and complete validation | Critical | Passed |

## Safety and test-data rules

- Use public example domains, injected fake sessions, and temporary local files only.
- Do not put tokens, signed URLs, private hostnames, or personal files in test data.
- The sitemap tests are offline; they do not request the example URLs shown below.

---

### [ADAPT-001-TC-01] Manual discovery returns ordered unique resources

- **Requirement IDs:** `ADAPT-001-FR-01`, `ADAPT-001-AC-01`
- **Component / Module:** Manual discovery
- **Priority:** High
- **Type:** Functional, Positive, Negative, Regression
- **Preconditions:** Project and test dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Discover a PDF URL with a fragment, the same URL without a fragment, and a relative text path with limit `2`. | Two resources are returned in first-seen order; the fragment and duplicate are removed. |
| **2** | Inspect source and media types. | Source is `manual`; PDF and text media types are guessed. |
| **3** | Try an unsupported scheme and an HTTP URL with embedded credentials. | Each request fails with a clear `ValueError`. |

- **Postconditions:** No external state changes.
- **Test Data:** `https://example.com/guide.pdf#page=2`, `docs/readme.txt`.
- **Evidence:** `tests/test_discovery_adapters.py`

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Ordered deduplication, limit, media-type, scheme, and credential cases passed.
- **Issue:** Not applicable

---

### [ADAPT-001-TC-02] Sitemap discovery follows robots and sitemap indexes safely

- **Requirement IDs:** `ADAPT-001-FR-02`–`ADAPT-001-FR-04`, `ADAPT-001-AC-02`
- **Component / Module:** Sitemap discovery
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** The injected mapping fetcher contains a robots file, sitemap index, and URL set.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Discover from `https://example.com/docs`. | Conventional sitemap candidates and `robots.txt` sitemap declarations are inspected. |
| **2** | Return a sitemap index containing same-origin and cross-origin children. | Only the same-origin child sitemap is fetched by default. |
| **3** | Return duplicate same-origin pages plus external and unsafe links. | Unique same-origin HTTP(S) pages are returned in source order. |
| **4** | Discover a gzip sitemap with output limit `1`. | The sitemap is decoded within its bound and only the first page is returned. |

- **Postconditions:** No real network request or file write occurs.
- **Test Data:** Synthetic robots and sitemap XML byte strings.
- **Evidence:** `tests/test_discovery_adapters.py`

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Robots, index, same-origin, deduplication, gzip, and limit cases passed.
- **Issue:** Not applicable

---

### [ADAPT-001-TC-03] Malformed and unsafe sitemap data is contained

- **Requirement IDs:** `ADAPT-001-FR-03`, `ADAPT-001-FR-04`, `ADAPT-001-NFR-02`, `ADAPT-001-AC-02`
- **Component / Module:** Sitemap parser and safety bounds
- **Priority:** Critical
- **Type:** Negative, Security, Boundary
- **Preconditions:** The injected fetcher can return controlled malformed bytes.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Return corrupt gzip content. | Discovery skips it without crashing. |
| **2** | Return compressed XML whose decoded size exceeds the limit. | Discovery skips it without reading unbounded decoded content. |
| **3** | Return XML with a document type/entity declaration. | The document is ignored. |
| **4** | Include an invalid port, embedded credentials, or a non-HTTP page URI. | Unsafe locations are omitted. |

- **Postconditions:** No external state changes.
- **Test Data:** Synthetic corrupt, oversized, and entity-bearing XML.
- **Evidence:** `tests/test_discovery_adapters.py`

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Corrupt gzip, decoded-size, entity, unsafe-scheme, and malformed-port cases passed.
- **Issue:** Not applicable

---

### [ADAPT-001-TC-04] HTTP fetching streams within limits and sanitizes failures

- **Requirement IDs:** `ADAPT-001-FR-05`, `ADAPT-001-NFR-02`, `ADAPT-001-NFR-03`, `ADAPT-001-AC-03`
- **Component / Module:** HTTP fetcher
- **Priority:** Critical
- **Type:** Functional, Negative, Security, Boundary
- **Preconditions:** A fake HTTP session is injected; no network is required.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Fetch a successful chunked text response. | Bytes, media type, filename, status, and size are normalized; the response closes. |
| **2** | Return a declared content length over the limit. | `FetchTooLargeError` is raised before content is accepted. |
| **3** | Stream bytes beyond the limit without a content length. | `FetchTooLargeError` is raised during streaming and the response closes. |
| **4** | Raise an upstream exception for a URL with query token and fragment. | The error contains the sanitized URL and exception type only. |

- **Postconditions:** Fake response is closed; no network state changes.
- **Test Data:** Small byte chunks and `https://example.com/file?token=secret#fragment`.
- **Evidence:** `tests/test_fetchers.py`

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Success, declared/streamed bounds, URL validation, closure, and sanitization cases passed.
- **Issue:** Not applicable

---

### [ADAPT-001-TC-05] Local fetching cannot escape its configured root

- **Requirement IDs:** `ADAPT-001-FR-06`, `ADAPT-001-AC-04`
- **Component / Module:** Local-file fetcher
- **Priority:** Critical
- **Type:** Functional, Negative, Security, Boundary
- **Preconditions:** Pytest creates a disposable root directory and files.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Fetch a relative path and local file URI inside the root. | Both return identical bytes with filename, media type, and byte metadata. |
| **2** | Fetch `../outside.txt`. | Fetch fails because the resolved path escapes the root. |
| **3** | Fetch a `file://server/...` URI. | Fetch fails because remote file authorities are unsupported. |
| **4** | Fetch a local file larger than the configured bound. | `FetchTooLargeError` is raised. |

- **Postconditions:** Temporary files are removed by pytest.
- **Test Data:** Disposable text and binary files.
- **Evidence:** `tests/test_fetchers.py`

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Relative/file URI, root escape, remote authority, and byte-limit cases passed.
- **Issue:** Not applicable

---

### [ADAPT-001-TC-06] Built-in factories and complete validation pass

- **Requirement IDs:** `ADAPT-001-FR-07`, `ADAPT-001-NFR-04`, `ADAPT-001-NFR-05`, `ADAPT-001-AC-05`
- **Component / Module:** Packaging and repository validation
- **Priority:** Critical
- **Type:** Functional, Regression, Packaging, Security
- **Preconditions:** Development and DocProc dependencies and Gitleaks are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | List and create the built-in discovery and fetch adapters. | Documented names resolve; unknown names fail clearly. |
| **2** | Run Ruff and the complete standalone and DocProc suites. | All checks pass. |
| **3** | Build and inspect a wheel. | Discovery and fetcher packages are included and importable. |
| **4** | Run the repository secret scan and review pull-request checks. | No leak is reported and required CI/CodeQL checks pass. |

- **Postconditions:** Build and test artifacts remain ignored or temporary.
- **Test Data:** Repository source only.
- **Current Status:** Passed
- **Evidence:** Local Ruff, pytest, wheel, and Gitleaks output; [PR #8](https://github.com/getanotherone/doc-harvester/pull/8).

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-04
- **Tester:** Automation
- **Actual Result:** Ruff passed; 21 focused, 106 standalone, and 107 DocProc tests passed;
  wheel contents/import and both Gitleaks scans passed. PR standalone 3.11/3.12, DocProc,
  secrets, and CodeQL checks passed.
- **Issue:** Not applicable

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Manual and sitemap discovery | `tests/test_discovery_adapters.py` |
| HTTP and local fetching | `tests/test_fetchers.py` |
| Factory selection and errors | Both adapter test modules |
| Complete regression and packaging | Local validation and CI |

## Traceability review

- [x] Every functional and API requirement has automated or review coverage.
- [x] Every acceptance criterion links to a manual and automated verification path.
- [x] Negative, boundary, filesystem, XML, and credential-leak cases are included.
- [x] Tests use disposable or synthetic data and require no credential.
- [x] Full CI evidence is linked before the phase is marked complete.
