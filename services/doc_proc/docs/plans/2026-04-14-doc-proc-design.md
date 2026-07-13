# DocProc — Document Processing Microservice Design

**Date:** 2026-04-14
**Status:** Approved
**Origin:** Extracted from an earlier integrated document-processing pipeline.

## Problem

The original document-processing pipeline grew organically and suffered from:
1. Tight coupling — `docling_document=None` as implicit routing signal between parser and chunker
2. 6 chunking strategies with no auto-selection logic
3. Hardcoded Russian construction domain patterns scattered across files
4. ProcessPool pickling constraints forcing architectural workarounds
5. No way to A/B compare strategies on the same document

## Architecture: Pipeline with Pluggable Stages

```
PARSE → FILTER → CHUNK → EMBED → EVALUATE
```

Each stage is a Python Protocol with typed inputs/outputs:

```
ParseResult    → list[ParsedElement]   # rows, tables, text blocks, images
FilterResult   → list[ParsedElement]   # same type, fewer elements
ChunkResult    → list[Chunk]           # text + metadata + section + type
EmbedResult    → list[EmbeddedChunk]   # Chunk + vector
EvalResult     → QualityReport         # metrics per chunk + aggregate
```

### Key Design Decisions

- `ParseResult.format_hint` is explicit (`tabular | document | mixed`) — no implicit routing
- `chunking/registry.py` provides `auto_select(format_hint, doc_stats)` for optimal strategy
- `pipeline.py` orchestrates all stages — single entry point
- `POST /pipeline/compare` runs N strategies on same doc for A/B testing
- No auth layer, no vision buffer, no normalization — pure document processing

## DB Schema (4 tables)

- **Document** — file metadata, status, parse_metadata JSONB
- **Chunk** — text + vector(1024) + strategy_used tag
- **Methodology** — single config JSONB blob (replaces 5 separate blobs)
- **ChunkEditHistory** — undo support

## Tech Stack

- FastAPI + SQLAlchemy 2.0 async + asyncpg + PostgreSQL 17 + pgvector
- Redis 7 (document queue), MinIO (file storage)
- Docling (OCR/complex docs), openpyxl (Excel streaming), pdfplumber (text PDF)
- BGE-M3 via Ollama (native macOS Metal GPU) / OpenAI-compatible embedding
- Alembic migrations

## Docker Services

postgres (5432), redis (6379), minio (9000/9001), backend (8000)
Ollama runs natively on macOS.

## Source

Extracted from an earlier internal document-processing implementation:
- `vision/` (2400 lines) → `parsing/`
- `services/chunking.py` + `chunking_v2.py` (1865 lines) → `chunking/`
- `embedding/` (530 lines) → `embedding/`
- `services/queue.py` + `worker.py` (1780 lines) → `queue/`
- `services/rag_quality.py` + `rag_optimization.py` (810 lines) → `evaluation/`
- `services/methodology.py` (457 lines) → `methodology` in API
