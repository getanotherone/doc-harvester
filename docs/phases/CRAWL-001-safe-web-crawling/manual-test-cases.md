# CRAWL-001 Manual Test Cases: Safe provider-neutral web crawling

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `CRAWL-001-TC-01` | Crawl a loopback documentation site | Critical | Passed by automation |
| `CRAWL-001-TC-02` | Enforce robots and crawl-fetch delay | Critical | Passed by automation |
| `CRAWL-001-TC-03` | Enforce traversal/filter/resource bounds | Critical | Passed by automation |
| `CRAWL-001-TC-04` | Block redirect escape before request | Critical | Passed by automation |
| `CRAWL-001-TC-05` | Verify CLI, output, configuration, and processing handoff | High | Passed |
| `CRAWL-001-TC-06` | Complete regression and release validation | Critical | Passed |

## Safety and test-data rules

- Use the loopback synthetic site before crawling any public host.
- Crawl a public site only when its terms and robots policy permit automated access.
- Keep robots enforcement enabled unless the site owner explicitly authorized the test.
- Start with a small page/depth limit and a delay of at least one second.
- Review manifests before sharing because resource URLs may contain private query parameters.
- Never crawl authenticated, customer, administration, logout, or destructive-action pages.

---

### [CRAWL-001-TC-01] Loopback site produces a process-compatible manifest

- **Requirement IDs:** `CRAWL-001-FR-01`, `CRAWL-001-FR-02`, `CRAWL-001-FR-07`, `CRAWL-001-FR-09`, `CRAWL-001-AC-01`
- **Component / Module:** HTML crawler, HTTP fetcher, source CLI
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** Synthetic server binds only to `127.0.0.1` and serves robots, root, guide, PDF, and disallowed routes.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Start the disposable loopback site and run `doc-harvester source crawl http://127.0.0.1:PORT/ --delay 0 --limit 10 --output /tmp/crawl.json`. | Command exits zero and writes version-1 JSON. |
| **2** | Inspect resources and server request log. | Root and guide HTML were fetched; linked PDF was discovered without fetch; private route was never requested. |
| **3** | Inspect crawl summary. | Fetched/discovered and robots counters match the observed requests; no raw errors appear. |
| **4** | Load `/tmp/crawl.json` through manifest validation. | Manifest is accepted by the same loader used by `source process`. |

- **Postconditions:** Disposable manifest exists; server is stopped.
- **Cleanup / Rollback:** Remove `/tmp/crawl.json`.
- **Test Data:** Synthetic HTML/robots/PDF bytes only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Three-resource manifest was produced from exactly robots, root, and guide requests; private/PDF routes were not fetched.
- **Evidence:** `tests/test_crawler_integration.py`

---

### [CRAWL-001-TC-02] Robots policy and effective delay are enforced

- **Requirement IDs:** `CRAWL-001-FR-03`, `CRAWL-001-FR-04`, `CRAWL-001-NFR-03`, `CRAWL-001-AC-02`
- **Component / Module:** Robots cache and rate control
- **Priority:** Critical
- **Type:** Security, Compliance, Negative and Positive
- **Preconditions:** Synthetic mapping has a disallowed path and crawl-delay greater than configured delay.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Crawl with robots enabled. | Robots is fetched once per origin; disallowed page is neither fetched nor emitted. |
| **2** | Compare injected sleep calls with configured and robots delays. | Each applicable wait uses the larger robots delay. |
| **3** | Make robots return 404/410. | Crawl proceeds because the policy file is absent. |
| **4** | Make robots fail for another reason or exceed its bound. | Crawl fails closed for that origin. |
| **5** | In an owner-authorized synthetic test only, repeat with `--ignore-robots`. | Page may be crawled and the flag is explicit in command history. |

- **Postconditions:** No external request is made.
- **Cleanup / Rollback:** None.
- **Test Data:** Synthetic robots text and mapping fetcher.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Disallow and crawl-delay passed; unavailable robots failed closed; 404 allowed; explicit opt-out worked.
- **Evidence:** `tests/test_crawlers.py`

---

### [CRAWL-001-TC-03] Scope, filters, depth, fetch, and link limits bound traversal

- **Requirement IDs:** `CRAWL-001-FR-02`, `CRAWL-001-FR-05`–`CRAWL-001-FR-07`, `CRAWL-001-AC-03`
- **Component / Module:** Queue, URL normalization, filters, media selection
- **Priority:** Critical
- **Type:** Boundary, Security, Negative
- **Preconditions:** Synthetic graph contains duplicate fragments, cycles, outside links, bridge pages, excluded paths, supported files, unsupported images, and excessive links.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Crawl with default origin restriction. | Outside-origin and unsafe-scheme links are never requested. |
| **2** | Apply include glob matching only a deep target. | Nonmatching bridge pages are traversed but omitted; target is emitted. |
| **3** | Apply exclusion glob to a bridge/private path. | Path and descendants are not requested. |
| **4** | Set small page/resource, depth, HTML/robots-byte, and link-per-page limits. | Each bound stops its corresponding expansion and `truncated` becomes true where applicable. |
| **5** | Inspect duplicate and file links. | Fragment duplicate is fetched once; supported file is emitted without fetch; unsupported image is counted/skipped. |

- **Postconditions:** Crawl remains within deterministic configured bounds.
- **Cleanup / Rollback:** None.
- **Test Data:** Synthetic mapping only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** All scope/filter/depth/fetch/link/file boundaries passed, including the no-match include crawl trap case.
- **Evidence:** `tests/test_crawlers.py`

---

### [CRAWL-001-TC-04] Cross-origin redirect is blocked before target contact

- **Requirement IDs:** `CRAWL-001-FR-08`, `CRAWL-001-NFR-03`, `CRAWL-001-AC-04`
- **Component / Module:** Manual HTTP redirect loop and crawler validator
- **Priority:** Critical
- **Type:** Security, Negative
- **Preconditions:** Sequential fake session returns a 302 from allowed origin to token-bearing outside URL.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Fetch allowed URL with crawler redirect validator. | Initial request receives redirect. |
| **2** | Inspect session calls. | Outside target was never contacted. |
| **3** | Inspect error/report. | Safe blocked counter/error contains neither target host nor token. |
| **4** | Repeat with a same-origin relative redirect. | Target is fetched within redirect limit and final URI is recorded. |

- **Postconditions:** No outside request exists.
- **Cleanup / Rollback:** None.
- **Test Data:** Fake `example.com` and `outside.test` responses.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Cross-origin target had zero calls and no leaked target/token; same-origin redirect succeeded.
- **Evidence:** `tests/test_fetchers.py`; crawler redirect test

---

### [CRAWL-001-TC-05] Public command/configuration and output safety work

- **Requirement IDs:** `CRAWL-001-FR-09`, `CRAWL-001-FR-10`, `CRAWL-001-API-01`–`CRAWL-001-API-06`, `CRAWL-001-AC-05`
- **Component / Module:** Factory, CLI parser, environment catalogue, package
- **Priority:** High
- **Type:** API, Configuration, Packaging, Regression
- **Preconditions:** Editable or wheel installation is active.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Import crawler/factory and inspect `source crawl --help`. | Public API and every documented control are available. |
| **2** | Run CLI with injected crawler and non-default controls. | Fetcher/crawler/policy receive exact timeout/byte/link/scope/pattern/delay/depth/page values. |
| **3** | Target an existing manifest without `--overwrite`. | Command fails and existing bytes remain unchanged. |
| **4** | Inspect `.env.example` and configuration guide. | Safe `DOC_HARVESTER_CRAWL_*` defaults are complete and non-secret. |
| **5** | Inspect/install wheel and run loopback crawl. | Crawler package/command are included and operational. |

- **Postconditions:** Existing manifest remains protected in the negative case.
- **Cleanup / Rollback:** Remove temporary wheel and manifest paths.
- **Test Data:** Fake/injected adapters and loopback site.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Factory/parser/policy forwarding, environment catalogue, pre-network file/symlink protection, processing-manifest compatibility, wheel contents, and extracted-wheel loopback crawl passed.
- **Evidence:** Crawler, source CLI, environment, packaging, and integration tests

---

### [CRAWL-001-TC-06] Complete repository and release validation pass

- **Requirement IDs:** `CRAWL-001-NFR-05`–`CRAWL-001-NFR-07`, `CRAWL-001-AC-06`
- **Component / Module:** Regression, packaging, security, CI
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Standalone and DocProc development dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build/inspect wheel and run extracted-wheel loopback crawl smoke. | New package/command work outside editable source. |
| **3** | Scan complete history and staged public tree. | No leak is found. |
| **4** | Review PR and post-merge CI/CodeQL. | Every required check passes. |

- **Postconditions:** Working tree contains only intended changes.
- **Cleanup / Rollback:** Remove temporary build/site/manifest artifacts.
- **Test Data:** Repository and synthetic loopback site only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Ruff, 60 focused tests, 260 standalone tests, 107 DocProc tests, wheel build/contents/extracted-wheel smoke, diff validation, and 52-commit history scan passed.
- **Evidence:** Local verification output and public PR #21 checks; squash merge `20d9742`

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Traversal, robots, scope, filters, bounds, redirect result | `tests/test_crawlers.py` |
| Real HTTP/CLI/manifest handoff | `tests/test_crawler_integration.py` |
| Pre-request redirects and bounded HTTP | `tests/test_fetchers.py` |
| Core depth contract | `tests/test_core_contracts.py` |
| CLI policy/configuration/output | `tests/test_source_cli.py`, `tests/test_env_example.py` |

## Traceability review

Every acceptance criterion maps to a manual case and automated evidence. Complete release
counts and public CI evidence will be recorded after verification.
