# Configuration

The root `.env.example` is the standalone application's configuration catalogue. It starts
with credential-free local defaults, groups optional integrations separately, and leaves
all secrets blank. DocProc is independently deployable and uses
`services/doc_proc/.env.example`; do not combine its database, Redis, MinIO, worker, and
embedding settings into the root file.

Copy the root template to `.env` only when file-based local configuration is useful. The
public CLI reads exported process variables and does not automatically load `.env`. Never
commit it, print it, attach it to an issue, or include it in a build.

## Credentials

| Variable | Required for | Notes |
|---|---|---|
| `YANDEX_DISK_TOKEN` | Yandex Disk upload/download | Not required for local-only crawling |
| `YANDEX_SEARCH_API_KEY` | Yandex Search discovery | Used with folder ID |
| `YANDEX_SEARCH_FOLDER_ID` | Yandex Search discovery | Yandex Cloud folder |
| `YANDEX_WIKI_TOKEN` | Wiki publishing | Keep separate from Disk credentials |
| `YANDEX_WIKI_CLOUD_ORG_ID` | Wiki publishing | Organization identifier |
| `CONFLUENCE_BASE_URL` | Confluence publishing | Site root such as `https://example.atlassian.net` |
| `CONFLUENCE_EMAIL` | Confluence publishing | Atlassian account email for basic authentication |
| `CONFLUENCE_API_TOKEN` | Confluence publishing | Atlassian API token, never an account password |
| `CONFLUENCE_SPACE_ID` | Confluence publishing | Numeric target space ID |
| `NOTION_TOKEN` | Notion publishing | Connection token with access to target pages |
| `SCRAPPER_API_KEY` | HTTP API | Use a randomly generated production value |

## Provider selection

Local storage and publication are safe defaults and require no credentials:

| Variable | Default | Effect |
|---|---|---|
| `DOC_HARVESTER_STORAGE` | `local` | `local`, `yandex`, or `s3` |
| `DOC_HARVESTER_LOCAL_STORAGE_ROOT` | `storage` | Filesystem provider root |
| `DOC_HARVESTER_PUBLISHER` | `local` | `local`, `yandex-wiki`, `confluence`, `notion`, or an installed plugin |
| `DOC_HARVESTER_PUBLISH_ROOT` | `published` | Local publisher root |

Credential-free `source` commands use these optional exported environment defaults. A CLI
flag with the corresponding name takes precedence.

| Variable | Default | CLI flag / effect |
|---|---:|---|
| `DOC_HARVESTER_DISCOVERY_LIMIT` | `100` | `--limit`; maximum manifest resources |
| `DOC_HARVESTER_MAX_SITEMAPS` | `20` | `--max-sitemaps`; sitemap traversal bound |
| `DOC_HARVESTER_MAX_SITEMAP_BYTES` | `10485760` | `--max-xml-bytes`; HTTP and decoded XML bound |
| `DOC_HARVESTER_FETCH_ROOT` | `.` | `--root`; permitted local-source root |
| `DOC_HARVESTER_MAX_FETCH_BYTES` | `52428800` | `--max-bytes`; maximum fetched bytes |
| `DOC_HARVESTER_HTTP_TIMEOUT` | `30` | `--timeout`; positive HTTP timeout in seconds |
| `DOC_HARVESTER_MAX_MANIFEST_BYTES` | `5242880` | `--max-manifest-bytes`; processing-manifest bound |
| `DOC_HARVESTER_MAX_PUBLICATION_DOCUMENT_BYTES` | `10485760` | `source render --max-document-bytes`; selected document JSON bound |
| `DOC_HARVESTER_MAX_PUBLICATION_BYTES` | `10485760` | `source render --max-publication-bytes`; rendered Markdown bound |
| `DOC_HARVESTER_MAX_PUBLICATION_BLOCKS` | `10000` | `source render --max-blocks`; normalized block bound |
| `DOC_HARVESTER_MAX_CHUNK_TOKENS` | `800` | `--max-tokens`; absolute processing chunk bound |
| `DOC_HARVESTER_MAX_PDF_PAGES` | `1000` | `--max-pdf-pages`; maximum pages accepted from one PDF |
| `DOC_HARVESTER_MAX_DOCX_BLOCKS` | `10000` | `--max-docx-blocks`; maximum normalized blocks from one DOCX |
| `DOC_HARVESTER_MAX_DOCX_UNCOMPRESSED_BYTES` | `104857600` | `--max-docx-uncompressed-bytes`; maximum expanded DOCX archive bytes |
| `DOC_HARVESTER_MAX_XLSX_SHEETS` | `100` | `--max-xlsx-sheets`; maximum worksheets from one XLSX |
| `DOC_HARVESTER_MAX_XLSX_ROWS` | `200000` | `--max-xlsx-rows`; maximum inspected rows from one XLSX |
| `DOC_HARVESTER_MAX_XLSX_CELLS` | `2000000` | `--max-xlsx-cells`; maximum inspected cells from one XLSX |
| `DOC_HARVESTER_MAX_XLSX_UNCOMPRESSED_BYTES` | `262144000` | `--max-xlsx-uncompressed-bytes`; maximum expanded XLSX bytes |
| `DOC_HARVESTER_XLSX_INCLUDE_HIDDEN` | `0` | `--include-hidden-xlsx-sheets`; include hidden sheets only when explicitly enabled |

The CLI reads exported process environment variables; it does not automatically load
`.env`. In zsh, load the safe values from a reviewed local file before running commands:

```bash
set -a
source .env
set +a
```

Invalid zero, negative, or non-numeric limit values are rejected during argument parsing.

S3-compatible storage uses `S3_BUCKET`, `S3_PREFIX`, `S3_ENDPOINT_URL`, `S3_REGION`,
`AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY`. Install its optional SDK with
`python -m pip install -e '.[s3]'`. AWS S3 can omit `S3_ENDPOINT_URL`; MinIO and other
compatible services should set it.

Confluence optionally uses `CONFLUENCE_PARENT_PAGE_ID` as the default parent for new
pages. Install Markdown conversion support with
`python -m pip install -e '.[confluence]'`. Notion defaults to
`NOTION_API_BASE=https://api.notion.com/v1` and `NOTION_API_VERSION=2026-03-11`; override
the version only when intentionally testing another supported Notion API version.

Provider destinations are relative to the provider root, bucket prefix, or remote service
namespace. Local adapters reject `..` traversal outside their configured root.
Documentation publishers do not change remote page permissions. Created pages inherit the
permissions of their configured space or parent.

## Credential-free source commands

Manual discovery accepts one or more paths or URLs and prints a versioned JSON manifest:

```bash
doc-harvester source discover manual README.md docs/architecture.md
```

Sitemap discovery is same-origin and includes `robots.txt` declarations by default:

```bash
doc-harvester source discover sitemap https://example.com/sitemap.xml \
  --limit 25 --output discovery.json
```

Use `--no-robots` or `--allow-cross-origin` only when that behavior is intentional. Fetch
one reviewed resource into an explicit output file:

```bash
doc-harvester source fetch README.md --root . --output /tmp/readme-copy.md
doc-harvester source fetch https://example.com/guide.pdf \
  --output /tmp/guide.pdf --max-bytes 10485760
```

An existing fetch output is preserved unless `--overwrite` is supplied. Discovery
manifests and fetch receipts preserve resource URIs, including query parameters that may
be required for retrieval; review them before sharing logs or artifacts publicly.

Process a reviewed version-1 manifest into a new local dataset:

```bash
doc-harvester source process discovery.json \
  --root . --output /tmp/doc-harvester-dataset --max-tokens 800
```

Processing currently supports plain text, Markdown, HTML, XHTML, XML, embedded-text PDFs,
DOCX main-body text/tables, and bounded XLSX worksheet rows. XLSX formulas are retained as
text and hidden sheets are excluded by default. A textless/image-only PDF is skipped with
reason `ocr_required`; the universal command does not invoke OCR. Legacy DOC, other Office,
legacy spreadsheet, image, and unsupported binary formats are reported as skipped. The
destination must not already exist; the command stages the complete report/documents/chunks
beside it and publishes the directory atomically. Original fetched bytes are not saved. A
mixed dataset is still published for review, while any failed resource makes the command
return non-zero.

Every processed resource also receives neutral metadata and a `quality.json`. Quality
findings do not block publication or change the exit status unless `--fail-on-quality` is
set. In enforced mode the review dataset is still retained, but the command returns non-zero
when at least one processed document fails its quality thresholds.

Store a reviewed dataset through a universal backend:

```bash
doc-harvester source store /tmp/doc-harvester-dataset \
  --storage local --local-root /tmp/doc-harvester-storage \
  --destination manual-test/run-001
```

`source store` requires a version-1 `processing-report.json`, verifies the referenced
document/chunk/quality files, rejects symbolic links and unsafe paths, and protects existing
objects by default. `--overwrite` is required to replace them. The processing report is
bounded by `DOC_HARVESTER_MAX_PROCESSING_REPORT_BYTES` (default 5 MiB).

Render one reviewed document for publication:

```bash
doc-harvester source render /tmp/doc-harvester-dataset \
  --document-index 0 --output /tmp/review.md
```

Source URI is omitted unless `--include-source-uri` is supplied after checking it for private
query parameters. Existing output requires `--overwrite`. Review the Markdown before using
`publish`; publication is dry-run by default and an existing destination requires
`--apply --update-existing`.

## Storage controls

| Variable | Default | Effect |
|---|---:|---|
| `DOC_HARVESTER_STORAGE` | `local` | Selected built-in backend |
| `DOC_HARVESTER_LOCAL_STORAGE_ROOT` | `storage` | Local backend root |
| `DOC_HARVESTER_MAX_PROCESSING_REPORT_BYTES` | `5242880` | Dataset validation bound |
| `DOC_HARVESTER_S3_BUCKET` | empty | S3/S3-compatible bucket |
| `DOC_HARVESTER_S3_PREFIX` | empty | Optional key prefix |
| `DOC_HARVESTER_S3_ENDPOINT_URL` | empty | Custom endpoint; omit for AWS S3 |
| `DOC_HARVESTER_S3_REGION` | empty | AWS region or provider-specific value |
| `AWS_ACCESS_KEY_ID` | empty | Standard SDK credential; secret-adjacent |
| `AWS_SECRET_ACCESS_KEY` | empty | Standard SDK secret credential |
| `AWS_SESSION_TOKEN` | empty | Optional temporary credential token |

Non-secret S3 fields can also be supplied through `source store --s3-*` options. Credentials
remain environment-only. Legacy `S3_BUCKET`, `S3_PREFIX`, `S3_ENDPOINT_URL`, and `S3_REGION`
are accepted for compatibility but the prefixed names above are canonical.

## Crawl controls

| Variable | Default | Effect |
|---|---:|---|
| `WEB_CRAWL_DELAY_SEC` | `5.0` | Delay between requests |
| `CRAWL_MAX_PAGES_PER_SOURCE` | `120` | Source traversal bound |
| `CRAWL_CHILD_PAGES` | `1` | Follow matching child pages |
| `CONSECUTIVE_404_THRESHOLD` | `20` | Abort persistently invalid URL sequences |
| `SITEMAP_ENABLED` | `1` | Include sitemap discovery |
| `SEARCH_DISCOVERY_ENABLED` | `1` | Include configured search provider |
| `UPLOAD_ENABLED` | `1` | Upload after processing; set `0` for local runs |

## Domain controls

The current defaults target electrical content:

| Variable | Default | Effect |
|---|---:|---|
| `ELECTRICAL_ONLY` | `1` | Apply electrical relevance filtering |
| `ELECTRICAL_SCORE_THRESHOLD` | `2` | Minimum document relevance score |
| `FOLLOW_CHILD_SCORE_THRESHOLD` | `0` | Minimum score for traversing child pages |
| `WEB_MIN_PRODUCT_SCORE` | `2` | Product-page URL threshold |

Use `config/profiles/electrical.json` as a profile example and
`config/profile.schema.json` as the machine-readable contract. A profile requires at least
one search query and may define priority terms, priority domains, crawl overrides, and
free-form metadata. Unknown top-level fields are rejected to catch misspellings.

The optional `crawl` object accepts `max_pages`, `file_score_threshold`,
`follow_child_score_threshold`, `web_min_product_score`, and `relevance_filter`. These
values are applied when `crawl` or `files` runs with that profile.

Validate profiles before discovery:

```bash
doc-harvester profile validate electrical
doc-harvester profile validate path/to/custom.json
```

## Quality controls

The manifest-driven `source process` command uses these universal settings:

| Variable | Default | Effect |
|---|---:|---|
| `DOC_HARVESTER_QUALITY_MIN_TOKENS` | `20` | Chunks below this token count are tiny |
| `DOC_HARVESTER_QUALITY_MAX_EMPTY_RATIO` | `0` | Maximum empty-chunk ratio |
| `DOC_HARVESTER_QUALITY_MAX_TINY_RATIO` | `0.8` | Maximum tiny-chunk ratio |
| `DOC_HARVESTER_QUALITY_MAX_DUPLICATE_RATIO` | `0.25` | Maximum duplicate-chunk ratio |
| `DOC_HARVESTER_QUALITY_MAX_NOISY_RATIO` | `0.1` | Maximum noisy-chunk ratio |
| `DOC_HARVESTER_QUALITY_MAX_OVERSIZED_RATIO` | `0` | Maximum oversized-chunk ratio |
| `DOC_HARVESTER_FAIL_ON_QUALITY` | `0` | Return non-zero for quality findings |

Ratio values must be between `0` and `1`. Matching CLI options override the environment.
The unprefixed `QUALITY_*` settings in `.env.example` belong to the legacy electrical
pipeline and do not configure `source process`.

## System dependencies

- Tesseract and Russian language data are required for OCR.
- Poppler is required by `pdf2image`.
- Playwright browser binaries are required only for `--spa` crawling.

Install Playwright's browser after package installation when SPA mode is needed:

```bash
playwright install chromium
```
