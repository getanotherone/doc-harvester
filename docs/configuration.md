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
| `SCRAPPER_API_KEY` | HTTP API | Use a randomly generated production value |

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

Use `config/profiles/electrical.json` as a profile example. General schema validation and
provider selection will replace environment-heavy configuration in the next phase.

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
