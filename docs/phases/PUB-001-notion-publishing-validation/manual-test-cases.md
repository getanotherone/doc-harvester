# PUB-001 Manual Test Cases: Notion Publishing Validation

These cases use synthetic IDs and filenames. Real tokens, page IDs, private URLs, raw
reports, and screenshots must remain local. Follow the
[Notion dry-run guide](../../notion-dry-run.md) for first-time setup.

## Execution summary

| Test case | Title | Current status |
|---|---|---|
| `PUB-001-TC-01` | Existing accessible page resolves in dry run | Passed (2026-07-15) |
| `PUB-001-TC-02` | Missing token fails before an API request | Not run |
| `PUB-001-TC-03` | Inaccessible or unknown page reports missing | Not run |
| `PUB-001-TC-04` | Missing publish map fails locally | Passed (2026-07-15) |
| `PUB-001-TC-05` | Invalid publish-map JSON fails locally | Not run |
| `PUB-001-TC-06` | Missing Markdown source is reported without API access | Not run |
| `PUB-001-TC-07` | Explicit apply updates a disposable existing page | Not run |
| `PUB-001-TC-08` | Child creation is gated during preview | Not run |
| `PUB-001-TC-09` | Explicit create flags create a disposable child page | Not run |
| `PUB-001-TC-10` | Credentials and private destinations remain uncommitted | Passed (2026-07-15) |
| `PUB-001-TC-11` | A repeated unchanged apply is skipped | Not run |

## Safety rules

- Run write cases only against disposable pages created for testing.
- Do not use a page containing content, child pages, or child databases that must be kept.
- Keep `.env`, `config/wiki_publish_map.json`, and `runs/` out of Git.
- Replace all real IDs and URLs with synthetic values in shared evidence.
- Stop if the active map does not clearly point to the intended disposable page.
- Do not execute `--apply` merely to complete this checklist; write validation must be an
  intentional phase decision.

---

### [PUB-001-TC-01] Existing accessible page resolves in dry run

- **Requirement IDs:** `PUB-001-FR-01`–`PUB-001-FR-05`, `PUB-001-FR-09`, `PUB-001-NFR-01`
- **Component / Module:** Notion publisher / batch publication
- **Priority:** Critical
- **Severity:** Critical
- **Type:** Functional, Positive, Regression
- **Automation Status:** Partially automated; real permissions require manual validation
- **Environment:** Local macOS terminal, Python 3.11, real disposable Notion page
- **Current Status:** Passed on 2026-07-15
- **Preconditions:**
  1. The Python virtual environment is active and the `wiki` extra is installed.
  2. `.env` contains a valid local `NOTION_TOKEN`.
  3. The connection has **Read content** capability and access to the disposable page.
  4. The ignored map selects `notion`, uses `README.md`, and contains `page:<real-page-id>`.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `pwd`. | The output is the `doc-harvester` repository root. |
| **2** | Run `python -m json.tool config/wiki_publish_map.json`. | Formatted JSON is printed with no syntax error. |
| **3** | Run `python scripts/publish_docs.py --map config/wiki_publish_map.json` without `--apply`. | The process completes, prints a report path, and reports `failed=0`. |
| **4** | Open the generated ignored report and inspect the page result. | `mode` is `dry_run`, `provider` is `notion`, and status is `would_update`. |
| **5** | Refresh or inspect the Notion page. | Page title and content are unchanged. No child page was created. |

- **Postconditions:** The connection remains read-only and the disposable page is unchanged.
- **Test Data:** `source=README.md`, `destination=page:<synthetic-page-id>`
- **Execution Record:** Passed. Sanitized result: `provider=notion`,
  `status=would_update`, external ID present, no error. Raw report remains under ignored
  `runs/` and is not committed.

---

### [PUB-001-TC-02] Missing token fails before an API request

- **Requirement IDs:** `PUB-001-FR-02`, `PUB-001-AC-04`, `PUB-001-NFR-02`
- **Component / Module:** Publisher factory / Notion authentication
- **Priority:** High
- **Severity:** High
- **Type:** Functional, Negative, Regression
- **Automation Status:** Candidate for automation
- **Environment:** Local terminal; no Notion capability required
- **Current Status:** Not run
- **Preconditions:** A valid local publish map exists. No apply flag will be used.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `NOTION_TOKEN= python scripts/publish_docs.py --map config/wiki_publish_map.json`. | The process exits with a clear `NOTION_TOKEN is required` error. |
| **2** | Inspect Notion. | No page content, title, permissions, or hierarchy changed. |
| **3** | Run the normal dry-run command again without the temporary empty override. | The token continues to load from `.env`; the file itself was not modified. |

- **Postconditions:** The valid local `.env` remains unchanged.
- **Test Data:** Empty process-scoped `NOTION_TOKEN`; no credential value is recorded.

---

### [PUB-001-TC-03] Inaccessible or unknown page reports missing

- **Requirement IDs:** `PUB-001-FR-04`, `PUB-001-FR-05`, `PUB-001-AC-04`
- **Component / Module:** Notion publisher / page lookup
- **Priority:** High
- **Severity:** Medium
- **Type:** Functional, Negative, Permissions
- **Automation Status:** Mocked lookup is automatable; real permissions require manual validation
- **Environment:** Local terminal and a valid read-capable Notion connection
- **Current Status:** Not run
- **Preconditions:** A backup of the working local map exists outside Git. No apply flag
  will be used.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | In the local map, replace the destination with a syntactically valid page ID that the connection cannot access. | The map remains valid JSON. |
| **2** | Run the dry-run command. | The process writes a report without attempting a remote write. |
| **3** | Inspect the per-page result. | Status is `missing`; no token appears in the result or error. |
| **4** | Restore the known accessible disposable page ID. | The next valid dry run can again produce `would_update`. |

- **Postconditions:** The working destination is restored and no Notion page changed.
- **Test Data:** `destination=page:aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee` or another
  synthetic/inaccessible ID.

---

### [PUB-001-TC-04] Missing publish map fails locally

- **Requirement IDs:** `PUB-001-FR-08`, `PUB-001-AC-01`, `PUB-001-AC-05`
- **Component / Module:** Batch map loader
- **Priority:** High
- **Severity:** Medium
- **Type:** Functional, Negative, Regression
- **Automation Status:** Candidate for automation
- **Environment:** Local terminal; no Notion access required
- **Current Status:** Passed on 2026-07-15
- **Preconditions:** The selected path does not exist.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `python scripts/publish_docs.py --map config/does-not-exist.json`. | The process exits with `FileNotFoundError` naming the missing map. |
| **2** | Inspect Notion if a connection is configured. | No API-backed change occurred. |

- **Postconditions:** No files or remote pages are created.
- **Test Data:** `config/does-not-exist.json`
- **Execution Record:** Passed. The original setup exposed the same failure when the map
  had been created in another repository; moving/copying it to the documented path allowed
  validation to continue.

---

### [PUB-001-TC-05] Invalid publish-map JSON fails locally

- **Requirement IDs:** `PUB-001-FR-08`, `PUB-001-AC-05`
- **Component / Module:** Batch map loader
- **Priority:** High
- **Severity:** Medium
- **Type:** Functional, Negative
- **Automation Status:** Candidate for automation
- **Environment:** Local terminal; no Notion access required
- **Current Status:** Not run
- **Preconditions:** A temporary test map can be created outside the repository.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Create `/tmp/doc-harvester-invalid-map.json` containing `{ invalid json }`. | The temporary file exists and contains no secret or real page ID. |
| **2** | Run `python -m json.tool /tmp/doc-harvester-invalid-map.json`. | JSON validation fails with a line/column error. |
| **3** | Run the publisher with that temporary map and no `--apply`. | The process exits with a JSON decoding error before constructing a publisher or contacting Notion. |

- **Postconditions / Cleanup:** Delete the synthetic temporary file using the operator's
  normal file-management method.
- **Test Data:** `{ invalid json }`

---

### [PUB-001-TC-06] Missing Markdown source is reported without API access

- **Requirement IDs:** `PUB-001-FR-08`, `PUB-001-FR-09`, `PUB-001-AC-05`
- **Component / Module:** Batch publisher / source validation
- **Priority:** High
- **Severity:** Medium
- **Type:** Functional, Negative, Regression
- **Automation Status:** Candidate for automation
- **Environment:** Local terminal
- **Current Status:** Not run
- **Preconditions:** A synthetic temporary map selects `notion` and uses an inaccessible
  local source path. It may use a synthetic destination ID because no API call is expected.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Set the map source to `does-not-exist.md`. | The map is valid JSON. |
| **2** | Run the dry-run command with that map. | The command writes a report; aggregate `failed` increases by one. |
| **3** | Inspect the page result. | Status is `failed` with reason `source file not found`. |
| **4** | Inspect Notion. | No lookup, update, or creation side effect is observed. |

- **Postconditions / Cleanup:** Remove the synthetic map or restore its original source.
- **Test Data:** `source=does-not-exist.md`

---

### [PUB-001-TC-07] Explicit apply updates a disposable existing page

- **Requirement IDs:** `PUB-001-FR-06`, `PUB-001-FR-09`, `PUB-001-API-04`, `PUB-001-API-06`, `PUB-001-AC-06`
- **Component / Module:** Notion publisher / Markdown replacement
- **Priority:** Critical
- **Severity:** Critical
- **Type:** Functional, Positive, Destructive, Regression
- **Automation Status:** Payload is automated; real write is manual
- **Environment:** Local terminal and a disposable Notion page
- **Current Status:** Not run
- **Preconditions:**
  1. The test page is disposable and contains no child page/database or content that must
     be retained.
  2. The connection has **Read content** and **Update content**.
  3. A dry run against the same destination has passed.
  4. The operator has reviewed the active map immediately before applying.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Create a small synthetic Markdown source with a unique heading and timestamp-free body. | The local file contains no private information. |
| **2** | Run the normal dry run. | Status is `would_update`; the Notion page remains unchanged. |
| **3** | Run `python scripts/publish_docs.py --map config/wiki_publish_map.json --apply`. | The report records `mode=apply`, status `updated`, and `failed=0`. |
| **4** | Open the disposable Notion page. | The page body matches the Markdown source; the title changes only if a title was configured. |
| **5** | Inspect page history. | The previous revision remains available for rollback. |

- **Postconditions / Cleanup:** Restore the page using Notion history or keep it clearly
  labeled as disposable. Remove **Update content** if it is no longer needed.
- **Test Data:** Synthetic Markdown and `page:<disposable-page-id>`.

---

### [PUB-001-TC-08] Child creation is gated during preview

- **Requirement IDs:** `PUB-001-FR-07`, `PUB-001-NFR-01`, `PUB-001-AC-07`
- **Component / Module:** Notion publisher / child-page creation gate
- **Priority:** Critical
- **Severity:** High
- **Type:** Functional, Positive, Negative, Safety, Regression
- **Automation Status:** Automated contract exists; real parent validation is manual
- **Environment:** Local terminal and a disposable Notion parent
- **Current Status:** Not run
- **Preconditions:** The local map uses `parent:<disposable-parent-id>`. No apply flag will
  be used.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run the dry run without `--create-missing`. | The result is `missing`; no child is created. |
| **2** | Run the dry run with `--create-missing` but without `--apply`. | The result is `would_create`; no child is created. |
| **3** | Inspect the parent page after both runs. | No new child page exists. |

- **Postconditions:** The parent hierarchy remains unchanged.
- **Test Data:** `destination=parent:<disposable-parent-id>` and a synthetic title.

---

### [PUB-001-TC-09] Explicit create flags create a disposable child page

- **Requirement IDs:** `PUB-001-FR-07`, `PUB-001-API-05`, `PUB-001-AC-07`
- **Component / Module:** Notion publisher / child-page creation
- **Priority:** High
- **Severity:** High
- **Type:** Functional, Positive, Destructive, Regression
- **Automation Status:** Payload is automated; real write is manual
- **Environment:** Local terminal and a disposable Notion parent
- **Current Status:** Not run
- **Preconditions:**
  1. `PUB-001-TC-08` has passed for the same parent.
  2. The connection has **Insert content** and access to the disposable parent.
  3. The source and title are synthetic and the new child is safe to remove.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Review the active `parent:` destination and source. | Both point only to disposable test resources. |
| **2** | Run the batch command with `--apply --create-missing`. | The report records `created`, returns an external page ID, and reports no failure. |
| **3** | Open the disposable parent. | Exactly one new child exists with the configured title and Markdown content. |

- **Postconditions / Cleanup:** Move the child to trash through Notion UI and remove
  **Insert content** if no longer needed.
- **Test Data:** `destination=parent:<disposable-parent-id>`, title
  `doc-harvester synthetic child`.

---

### [PUB-001-TC-10] Credentials and private destinations remain uncommitted

- **Requirement IDs:** `PUB-001-NFR-02`, `PUB-001-NFR-03`, `PUB-001-AC-08`
- **Component / Module:** Repository hygiene / reporting
- **Priority:** Critical
- **Severity:** Critical
- **Type:** Security, Privacy, Regression
- **Automation Status:** Candidate for CI policy checks
- **Environment:** Local Git worktree after manual validation
- **Current Status:** Passed on 2026-07-15
- **Preconditions:** Local `.env`, publish map, and at least one report exist.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `git check-ignore -v .env config/wiki_publish_map.json runs/`. | Git identifies ignore rules for all three paths. |
| **2** | Run `git status --short`. | The local secret/config/report paths are absent from tracked changes. |
| **3** | Inspect the report's key names and error fields without copying private values into shared evidence. | No token or authorization header is present. |
| **4** | Review committed examples and phase documentation. | Only synthetic tokens, IDs, domains, and content appear. |

- **Postconditions:** Private artifacts remain local and ignored.
- **Test Data:** Existing local artifacts; no value is copied into this test record.
- **Execution Record:** Passed. Git ignore rules matched `.env`, the local publish map,
  and `runs/`; the dry-run report contained no token or authorization key. Only this
  sanitized result is committed.

---

### [PUB-001-TC-11] A repeated unchanged apply is skipped

- **Requirement IDs:** `PUB-001-FR-10`, `PUB-001-NFR-06`
- **Component / Module:** Batch publisher / content-hash state
- **Priority:** Medium
- **Severity:** Low
- **Type:** Functional, Positive, Regression, Idempotency
- **Automation Status:** Candidate for automation
- **Environment:** Local terminal and a disposable existing Notion page
- **Current Status:** Not run
- **Preconditions:** `PUB-001-TC-07` has passed, the local source has not changed, and the
  ignored hash state from that apply run is present.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Without changing the source or map, run the same command with `--apply` again. | The report records `unchanged`; no update request is required. |
| **2** | Inspect the Notion page and its history. | Content is unchanged and no additional content revision is attributable to the second run. |
| **3** | Change the synthetic source and run a dry run. | The preview remains safe and reports `would_update`. |

- **Postconditions / Cleanup:** Restore or remove the disposable test page and synthetic
  source according to the write-test cleanup plan.
- **Test Data:** Same source, destination, and title as the successful disposable apply.

## Automated coverage references

The following automated tests complement but do not replace the live manual cases:

| Behavior | Automated test |
|---|---|
| Notion Markdown replacement payload and API version | `tests/test_publishers.py::test_notion_replaces_existing_page_with_native_markdown` |
| Notion child preview and creation payload | `tests/test_publishers.py::test_notion_creates_child_page_from_parent_destination` |
| Publisher discovery and built-in registration protection | `tests/test_publishers.py::test_publisher_factory_supports_registration_and_lists_builtins` |
| Generic CLI publisher selection | `tests/test_cli.py::test_cli_accepts_installed_publisher_name` |

## Traceability notes

- API header and payload requirements are primarily verified by automated contract tests.
- Real authentication, page access, permissions, and lack of external side effects require
  manual validation against a disposable workspace.
- Any failed manual case should link to an issue before the phase status changes to
  complete.
