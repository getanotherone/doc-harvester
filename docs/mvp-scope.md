# CLI-first MVP scope

Version `0.2.0` is the first open-source MVP of doc-harvester. The MVP is a local,
review-gated command-line workflow for turning static technical documents and websites into
structured chunk datasets. It is intended for evaluation, contributor development, and
small controlled ingestion jobs—not unattended production crawling.

## Supported user outcome

An operator can install the base package without credentials and:

1. discover explicit resources, read a sitemap, or crawl a static same-origin site;
2. fetch bounded HTTP or root-confined local files;
3. extract HTML/XML, text, digital-text PDF, DOCX, and XLSX content;
4. create bounded chunks with neutral metadata and quality findings;
5. inspect a privacy-safe dataset inventory;
6. store the reviewed dataset locally;
7. render one selected document and preview publication without applying it.

The [credential-free golden path](golden-path.md) demonstrates this outcome using only
repository-owned synthetic fixtures.

## Safety defaults

- Exact seed-origin crawling with robots enforcement and a one-second delay.
- Explicit page, depth, response-byte, robots-byte, link-count, manifest, format, and chunk
  limits.
- No embedded URL credentials and no cross-origin redirect escape.
- Atomic local dataset/render writes and no overwrite by default.
- Content-free inspection and source-URI exclusion by default.
- Local publication preview unless `--apply` is explicitly supplied.
- No cloud credentials or remote provider required by the MVP path.

## Supported formats and limitations

| Capability | MVP support | Limitation |
|---|---|---|
| HTML/XML/text | Supported | Static response content only; no JavaScript rendering in the universal crawler. |
| PDF | Digital text | Image-only PDFs return `ocr_required`; OCR is a separate legacy extra. |
| DOCX | Paragraphs, headings, lists, tables | No legacy `.doc`, drawings, equations, or tracked-change policy. |
| XLSX | Bounded worksheet rows/cells | Formulas are preserved but not evaluated; no legacy `.xls` or macros. |
| Crawling | Sequential, bounded, robots-aware | No persistent in-stage resume, concurrency, or browser rendering. |
| Storage | Local validated datasets | S3/Yandex adapters are optional and require separate operator validation. |
| Publishing | Local preview plus optional adapters | Every remote write requires provider setup and explicit apply permission. |
| API/DocProc | Retained, independently tested | The MVP promise is the universal CLI, not a production hosted service. |

## Optional installations

The base wheel excludes the largest legacy-only runtime dependencies:

```bash
pip install 'doc-harvester[browser]'  # legacy SPA crawling
pip install 'doc-harvester[ocr]'      # legacy PDF OCR Python libraries
pip install 'doc-harvester[legacy]'   # both groups
```

Browser mode also needs a Playwright browser. OCR needs Poppler and Tesseract system
binaries. API, S3, and documentation-provider extras remain independently selectable.

## MVP release criteria

- [x] Credential-free golden path passes from crawl through publication preview.
- [x] All supported formats have bounded automated extraction coverage.
- [x] A real public technical page crawls and processes within the absolute chunk ceiling.
- [x] Base wheel builds, installs cleanly, and omits browser/OCR dependencies.
- [x] Python 3.11/3.12, DocProc, secret scan, and CodeQL checks are configured.
- [x] Security, contribution, configuration, backup, and manual-test documentation exists.
- [x] Version `0.2.0` candidate is merged to `main` with all public checks green.
- [x] Git tag and GitHub release are created from the verified merge commit.

PyPI publication is handled by the post-MVP
[DIST-001 distribution phase](phases/DIST-001-pypi-community-launch/task-summary.md).
Remote-provider certification, production SLAs, and automatic application deployment remain
outside the `0.2.0` MVP promise.
