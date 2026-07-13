# doc-harvester

`doc-harvester` is an alpha-stage ingestion pipeline for turning technical documents and
web pages into structured, RAG-ready JSON chunks. It combines discovery, crawling,
memory-safe PDF extraction, HTML cleanup, token-aware chunking, metadata enrichment,
quality checks, and optional publishing to Yandex services.

The project was initially tuned for Russian electrical-engineering material. The core is
being generalized through profiles and provider interfaces; it is not yet a universal
scraper for every website or document type.

## Capabilities

- Crawl HTML catalogues and follow relevant child pages.
- Find linked PDF, DOCX, XLSX, HTML, and XML resources.
- Extract large PDFs page by page with OCR fallback and resumable unit files.
- Remove navigation, commercial boilerplate, malformed OCR, and CID garbage.
- Preserve tables and normative clauses during token-aware chunking.
- Add retrieval metadata such as document, page, section, vendor, standard, year,
  language, source type, and quality status.
- Store output locally, on Yandex Disk, or in S3-compatible object storage.
- Publish generated documentation locally, to Yandex Wiki, Confluence Cloud, Notion, or
  installed third-party services through provider adapters.
- Run a FastAPI service and an optional, independently deployable DocProc service.

## Quick Start

Requirements: Python 3.11+, Tesseract, and Poppler. OCR binaries are optional for the
offline demo but required for image-only PDFs.

```bash
git clone https://github.com/getanotherone/doc-harvester.git
cd doc-harvester

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'

doc-harvester demo
```

The demo uses embedded HTML, requires no credentials or network access, and writes
`demo-output/chunks.json`.

## CLI

```bash
# Crawl locally without uploading
doc-harvester crawl https://example.com/catalog/ --no-upload

# Crawl and copy generated artifacts into local provider storage
doc-harvester crawl https://example.com/catalog/ --storage local

# Discover URLs through Yandex Search API
doc-harvester discover example.com --term "technical catalogue" --output discovery.json

# Process linked files and store results locally (the safe default)
doc-harvester files https://example.com/downloads/ --storage local

# Store an already processed dataset with any configured adapter
doc-harvester upload electrical/example.com --storage local
doc-harvester upload electrical/example.com --storage yandex
doc-harvester upload electrical/example.com --storage s3

# Validate or list discovery profiles
doc-harvester profile validate electrical
doc-harvester profile list

# Preview or apply publication of one Markdown artifact
doc-harvester publish README.md docs/readme
doc-harvester publish README.md docs/readme --apply

# Run the optional API
python -m pip install -e '.[api]'
SCRAPPER_API_KEY=change-me doc-harvester api
```

Copy `.env.example` to `.env` for local configuration. Never commit `.env`.

## Output Model

Chunks use a retrieval-oriented JSON model:

```json
{
  "document": "catalog.pdf",
  "page": 12,
  "section": "Automatic circuit breakers",
  "chunk_index": 4,
  "text": "...",
  "doc_type": "catalog",
  "vendor": "",
  "standard_id": "",
  "year": null,
  "lang": "en",
  "source_type": "pdf",
  "quality_status": "passed"
}
```

Not every extractor can populate every field. Missing values remain empty or `null`.

## Architecture

```text
discovery -> crawler/fetcher -> extractor -> unit JSON
         -> chunker -> metadata/quality -> storage -> publisher
```

- `src/`: standalone crawler, extractors, chunker, quality checks, and providers.
- `src/doc_harvester/`: public package and CLI.
- `api/`: optional FastAPI wrapper for scraper operations.
- `services/doc_proc/`: separate document-processing service with richer parsing,
  chunking strategies, embeddings, PostgreSQL, Redis, and MinIO.
- `config/profiles/`: domain discovery profiles.
- `scripts/`: advanced operational and Wiki automation commands.

Yandex Disk and documentation services are optional adapters, not requirements for
extraction and chunking. Public storage and publisher contracts are available under
`doc_harvester.storage` and `doc_harvester.publishers`. S3 support is installed with
`pip install -e '.[s3]'`; documentation automation uses `pip install -e '.[wiki]'`.

## Development

```bash
python -m pip install -e '.[dev,api]'
ruff check .
pytest -q
PYTHONPATH=services/doc_proc/backend/src pytest -q services/doc_proc/tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and the
[documentation index](docs/README.md).

## Security And Responsible Crawling

- Respect website terms, robots policies, copyright, and applicable laws.
- Use conservative crawl delays and bounded page limits.
- Do not publish downloaded documents unless their licenses permit redistribution.
- Keep credentials in environment variables or a secret manager.
- Review generated chunks before using them in production retrieval systems.

## Status

Version `0.1.0` is an alpha release. APIs, configuration, and output schemas may change.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE).
