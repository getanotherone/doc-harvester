# Configuration

Copy `.env.example` to `.env` for local development. The application does not automatically
make `.env` safe: never commit it, print it, attach it to an issue, or include it in a build.

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

`QUALITY_MIN_TOKENS`, `QUALITY_MAX_EMPTY_RATIO`, `QUALITY_MAX_TINY_RATIO`,
`QUALITY_MAX_DUPLICATE_RATIO`, and `QUALITY_MAX_NOISY_RATIO` configure local quality gates.
Defaults are defined in `src/quality_eval.py`.

## System dependencies

- Tesseract and Russian language data are required for OCR.
- Poppler is required by `pdf2image`.
- Playwright browser binaries are required only for `--spa` crawling.

Install Playwright's browser after package installation when SPA mode is needed:

```bash
playwright install chromium
```
