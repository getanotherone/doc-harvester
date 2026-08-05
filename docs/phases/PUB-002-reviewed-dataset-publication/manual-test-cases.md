# PUB-002 Manual Test Cases: Reviewed dataset publication

Related task summary: [task-summary.md](task-summary.md)

## Execution summary

| Test case | Title | Priority | Current status |
|---|---|---|---|
| `PUB-002-TC-01` | Render one reviewed document | Critical | Passed by automation |
| `PUB-002-TC-02` | Protect source URI privacy | Critical | Passed by automation |
| `PUB-002-TC-03` | Reject unsafe or bounded inputs | Critical | Passed by automation |
| `PUB-002-TC-04` | Preview, create, and explicitly update locally | Critical | Passed by automation |
| `PUB-002-TC-05` | Preserve destination on local write failure | High | Passed by automation |
| `PUB-002-TC-06` | Complete regression and release validation | Critical | Passed locally; PR pending |

## Safety and test-data rules

- Use only synthetic or legally reviewed content.
- Render and publish locally before configuring any remote provider.
- Inspect the complete Markdown artifact before apply mode.
- Never include a real token-bearing URI in committed test evidence.
- Use disposable `/tmp` paths and do not delete a non-test destination during cleanup.

---

### [PUB-002-TC-01] Valid processed document renders for review

- **Requirement IDs:** `PUB-002-FR-01`, `PUB-002-FR-02`, `PUB-002-FR-09`, `PUB-002-AC-01`
- **Component / Module:** Dataset publication renderer, `source render`
- **Priority:** Critical
- **Type:** Functional, Integration, Positive
- **Preconditions:** A reviewed version-1 dataset exists at `/tmp/dataset` with processed index `0`.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `doc-harvester source render /tmp/dataset --document-index 0 --output /tmp/review.md`. | Command exits zero and prints a JSON receipt. |
| **2** | Inspect receipt fields. | Schema version, index, title, quality, output, byte count, and SHA-256 are present. |
| **3** | Open `/tmp/review.md`. | Generated warning, title, document index, quality status, and normalized content are readable. |
| **4** | Compare the receipt hash/bytes with the file. | Values match exactly; source dataset is unchanged. |

- **Postconditions:** One unpublished review artifact exists.
- **Cleanup / Rollback:** Remove `/tmp/review.md` after the publication cases.
- **Test Data:** Synthetic single-document dataset.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation plus local CLI smoke
- **Actual Result:** Earlier reviewed README dataset rendered with an accurate 7,990-byte receipt and no source URI.
- **Evidence:** `tests/test_dataset_publication.py`; sanitized CLI output

---

### [PUB-002-TC-02] Source URI remains private unless explicitly included

- **Requirement IDs:** `PUB-002-FR-03`, `PUB-002-NFR-03`, `PUB-002-NFR-04`, `PUB-002-AC-02`
- **Component / Module:** Renderer privacy policy
- **Priority:** Critical
- **Type:** Security, Privacy, Negative and Positive
- **Preconditions:** Synthetic document URI contains `?token=fake-private-value`.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Render normally and search the Markdown/receipt for the URI or fake token. | Neither output contains the URI/token. |
| **2** | Review that the synthetic URI is safe, then render a new output with `--include-source-uri`. | Markdown contains the URI; receipt only records `source_uri_included: true`. |

- **Postconditions:** Default output contains no source address.
- **Cleanup / Rollback:** Remove both disposable outputs.
- **Test Data:** Fake `example.test` URI only.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Token-bearing synthetic URI was absent by default and present only in the explicitly opted-in Markdown.
- **Evidence:** `test_render_dataset_document_creates_reviewable_markdown_without_source_uri`; opt-in test

---

### [PUB-002-TC-03] Unsafe, invalid, and oversized rendering is rejected

- **Requirement IDs:** `PUB-002-FR-01`, `PUB-002-FR-04`–`PUB-002-FR-06`, `PUB-002-AC-03`
- **Component / Module:** Dataset validation and filesystem boundaries
- **Priority:** Critical
- **Type:** Negative, Boundary, Security
- **Preconditions:** Disposable dataset variants and output paths exist.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Select a negative, missing, skipped, or failed index. | Command returns non-zero without an output. |
| **2** | Exceed a document, block, or rendered-byte bound. | Command returns non-zero and names the exceeded bound. |
| **3** | Render to an existing file without `--overwrite`. | Existing bytes remain unchanged. |
| **4** | Render inside the dataset or to an output file that is a symlink. | Path is rejected without modifying source or link target. |
| **5** | Intentionally rerun against a disposable existing file with `--overwrite`. | Complete new file atomically replaces it. |

- **Postconditions:** Rejected cases leave source and previous outputs intact.
- **Cleanup / Rollback:** Remove disposable inputs and outputs.
- **Test Data:** Synthetic malformed/bounded datasets.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Index, block bound, dataset boundary, existing output, dataset-root symlink, and output symlink protections passed.
- **Evidence:** `tests/test_dataset_publication.py`

---

### [PUB-002-TC-04] Local publication previews, creates, and explicitly updates

- **Requirement IDs:** `PUB-002-FR-07`, `PUB-002-FR-08`, `PUB-002-AC-04`
- **Component / Module:** Publisher CLI and local adapter
- **Priority:** Critical
- **Type:** Functional, Safety, Regression
- **Preconditions:** `/tmp/review.md` was inspected; `/tmp/published` is disposable.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run `doc-harvester publish /tmp/review.md guides/review --publisher local --local-root /tmp/published`. | Status is `would_create`; no destination file exists. |
| **2** | Repeat with `--apply`. | Status is `published`; destination bytes match the reviewed file. |
| **3** | Change source and repeat with `--apply` only. | Command returns non-zero, mentions `--update-existing`, and destination remains unchanged. |
| **4** | Repeat intentionally with `--apply --update-existing`. | Updated bytes are published atomically. |
| **5** | Try an empty/traversal/symlink destination. | Command fails without writing outside the local root. |

- **Postconditions:** One explicitly approved local publication exists.
- **Cleanup / Rollback:** Remove `/tmp/published` only.
- **Test Data:** Reviewed synthetic Markdown.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation plus local CLI smoke
- **Actual Result:** Preview/create produced byte-identical local Markdown; repeat apply was blocked and explicit update succeeded.
- **Evidence:** `tests/test_cli.py`; `/tmp` smoke summarized without committing artifacts

---

### [PUB-002-TC-05] Failed local replacement preserves previous content

- **Requirement IDs:** `PUB-002-FR-05`, `PUB-002-NFR-02`, `PUB-002-AC-05`
- **Component / Module:** Local publisher atomic write
- **Priority:** High
- **Type:** Reliability, Fault injection
- **Preconditions:** Automated test can inject a copy failure; existing destination contains known bytes.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Start an apply while forcing the temporary-file copy to fail. | Operation raises/fails before replacement. |
| **2** | Read the existing destination and list temporary files. | Original bytes remain and no temporary file remains. |

- **Postconditions:** Existing destination is intact.
- **Cleanup / Rollback:** None beyond the temporary test directory.
- **Test Data:** `keep` destination and `new` source.

### Execution record

- **Status:** Passed
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Injected copy failure retained existing bytes and cleaned the temporary file.
- **Evidence:** `test_local_publisher_atomic_failure_preserves_existing_destination`

---

### [PUB-002-TC-06] Complete repository and release validation pass

- **Requirement IDs:** `PUB-002-NFR-05`, `PUB-002-NFR-06`, `PUB-002-AC-06`
- **Component / Module:** Regression, packaging, security, CI
- **Priority:** Critical
- **Type:** Regression, Packaging, Security
- **Preconditions:** Standalone and DocProc development dependencies are installed.

### Steps to reproduce

| # | Action / Step | Expected Result |
|---:|---|---|
| **1** | Run Ruff and complete standalone/DocProc suites. | All checks pass. |
| **2** | Build, inspect, and install the wheel; run render and local publish smoke. | New module/command are packaged and operational. |
| **3** | Scan complete history and the candidate public tree for secrets. | No leak is found. |
| **4** | Review PR and post-merge CI/CodeQL. | Every required check passes. |

- **Postconditions:** Only ignored or temporary test artifacts exist.
- **Cleanup / Rollback:** Remove temporary package, render, and publication paths.
- **Test Data:** Repository and synthetic dataset only.

### Execution record

- **Status:** Passed locally; PR and post-merge pending
- **Executed:** 2026-08-05
- **Tester:** Automation
- **Actual Result:** Ruff, 235 standalone tests, 107 DocProc tests, wheel build/contents/extracted-wheel smoke, diff validation, and 48-commit history scan passed. Working-directory scan found only the ignored local `.env`, which is not part of the public candidate tree.
- **Evidence:** Local verification output; public CI link pending

## Automated coverage references

| Requirement / behavior | Automated test or check |
|---|---|
| Rendering, privacy, bounds, conflict, CLI | `tests/test_dataset_publication.py` |
| Atomic/symlink-safe local publisher | `tests/test_publishers.py` |
| Explicit existing-destination update | `tests/test_cli.py` |
| Public parser and safe environment catalogue | `tests/test_source_cli.py`, `tests/test_env_example.py` |

## Traceability review

Every acceptance criterion maps to a manual case and focused automated evidence. Final
execution counts and public CI evidence will be recorded after release verification.
