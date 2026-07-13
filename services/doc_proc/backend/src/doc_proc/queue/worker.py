"""Async document processing worker.

Dequeues tasks from Redis, processes them through the pipeline,
stores results in PostgreSQL. Uses ProcessPool for CPU-heavy parsing.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from doc_proc.config import settings
from doc_proc.db.enums import DocumentStatus
from doc_proc.queue.service import DocumentQueueService, QueueTask

logger = logging.getLogger(__name__)


def calculate_timeout(filename: str, cell_count: int = 0, file_size_mb: float = 0) -> int:
    """Calculate per-file processing timeout in seconds."""
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext in ("xlsx", "xls", "csv"):
        timeout = 120 + (cell_count * 2) // 1000
    elif ext == "pdf":
        timeout = 300 + int(file_size_mb * 10)
    else:
        timeout = 600

    return max(120, min(7200, timeout))


class DocumentWorker:
    def __init__(self, max_concurrent: int | None = None):
        self.max_concurrent = max_concurrent or settings.worker_max_concurrent
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._running = False
        self._task: asyncio.Task | None = None
        self._active_tasks: set[asyncio.Task] = set()
        self.queue = DocumentQueueService()

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Document worker started (max_concurrent=%d)", self.max_concurrent)

    async def stop(self, timeout: float = 30.0):
        self._running = False
        if self._active_tasks:
            await asyncio.wait(self._active_tasks, timeout=timeout)
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.queue.close()
        logger.info("Document worker stopped")

    async def _run_loop(self):
        while self._running:
            try:
                await self._semaphore.acquire()
                task = await self.queue.dequeue(timeout=2)
                if task is None:
                    self._semaphore.release()
                    continue

                process_task = asyncio.create_task(self._process_with_semaphore(task))
                self._active_tasks.add(process_task)
                process_task.add_done_callback(self._active_tasks.discard)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker loop error: %s", e)
                self._semaphore.release()
                await asyncio.sleep(1)

    async def _process_with_semaphore(self, task: QueueTask):
        try:
            await self._process_task(task)
        except Exception as e:
            logger.error("Task %s failed: %s", task.task_id, e)
            await self.queue.fail(task.task_id, str(e))
        finally:
            self._semaphore.release()

    async def _process_task(self, task: QueueTask):
        from doc_proc.db import models as m
        from doc_proc.db.session import async_session_factory
        from doc_proc.embedding.factory import create_embedding_provider
        from doc_proc.pipeline import Pipeline, PipelineConfig
        from doc_proc.storage.minio import download_file

        # Step 1: Fetch file
        await self.queue.update_progress(task.task_id, 2, "Fetching file")
        content = await asyncio.get_running_loop().run_in_executor(
            None, download_file, task.file_path
        )
        size_mb = len(content) / (1024 * 1024)
        await self.queue.update_progress(
            task.task_id, 5, "Validating",
            {"size_mb": round(size_mb, 1)},
        )

        # Step 2: Check cancellation
        current = await self.queue.get_task(task.task_id)
        if current and current.status == "failed" and "Cancelled" in current.error:
            raise asyncio.CancelledError("Cancelled by user")

        # Step 3: Parse + chunk (10% → 40%)
        await self.queue.update_progress(task.task_id, 10, "Parsing document")

        config = PipelineConfig(
            doc_title=task.filename,
            embed=False,  # We embed separately with progress
        )

        # Apply methodology config if provided
        methodology_config = task.metadata.get("methodology_config")
        if methodology_config:
            for key, value in methodology_config.items():
                if hasattr(config, key):
                    setattr(config, key, value)

        pipeline = Pipeline(config)
        parse_result = pipeline.parse(content, task.filename)
        await self.queue.update_progress(task.task_id, 30, "Parsed", {
            "elements": len(parse_result.elements),
            "format": parse_result.format_hint,
        })

        parse_result = pipeline.filter(parse_result)
        chunk_result = pipeline.chunk(parse_result)

        # Enrich chunks with domain metadata (vendor, standard, doc_type, lang)
        if pipeline.config.extract_domain_metadata:
            chunk_result = pipeline.enrich_metadata(chunk_result, task.filename)

        await self.queue.update_progress(task.task_id, 40, "Chunked", {
            "chunks": len(chunk_result.chunks),
            "strategy": chunk_result.strategy_used,
        })

        # Check chunk limit
        if len(chunk_result.chunks) > settings.worker_max_chunks:
            raise ValueError(
                f"Document produces {len(chunk_result.chunks)} chunks "
                f"(limit: {settings.worker_max_chunks})"
            )

        # Step 4: Embed with progress (40% → 90%)
        embedder = create_embedding_provider()
        batch_size = settings.embedding_batch_size
        all_embeddings: list[list[float]] = []
        total = len(chunk_result.chunks)

        for i in range(0, total, batch_size):
            batch_texts = [c.text for c in chunk_result.chunks[i : i + batch_size]]
            batch_embeddings = await embedder.embed_batch(batch_texts)
            all_embeddings.extend(batch_embeddings)

            done = min(i + batch_size, total)
            pct = 40 + int(50 * done / max(total, 1))
            await self.queue.update_progress(
                task.task_id, pct, "Embedding",
                {"chunks_done": done, "total_chunks": total},
            )

            # Check cancellation between batches
            current = await self.queue.get_task(task.task_id)
            if current and current.status == "failed" and "Cancelled" in current.error:
                raise asyncio.CancelledError("Cancelled by user")

        # Step 5: Save to DB (90% → 100%)
        await self.queue.update_progress(task.task_id, 90, "Saving to database")

        async with async_session_factory() as db:
            # Update document
            from sqlalchemy import select
            stmt = select(m.Document).where(m.Document.id == uuid.UUID(task.document_id))
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()

            if not doc:
                raise ValueError(
                    f"Document {task.document_id} not found in DB (deleted before processing?)"
                )

            if doc:
                doc.status = DocumentStatus.completed
                doc.completed_at = datetime.now(UTC)
                doc.total_rows = len(parse_result.elements)
                doc.page_count = parse_result.page_count
                doc.tables_count = parse_result.tables_count
                doc.has_ocr = parse_result.has_ocr
                doc.parse_metadata = {
                    "format_hint": parse_result.format_hint,
                    "parser": parse_result.metadata.get("parser", ""),
                    "strategy_used": chunk_result.strategy_used,
                }

            # Insert chunks
            from doc_proc.models import estimate_tokens

            for i, (chunk, embedding) in enumerate(
                zip(chunk_result.chunks, all_embeddings)
            ):
                db_chunk = m.Chunk(
                    document_id=uuid.UUID(task.document_id),
                    chunk_index=i,
                    chunk_type=chunk.chunk_type,
                    text=chunk.text,
                    context_header=chunk.context_header or None,
                    section=chunk.section or None,
                    page=chunk.page,
                    chunk_metadata=chunk.metadata or None,
                    embedding=embedding,
                    token_count=chunk.token_count or estimate_tokens(chunk.text),
                    strategy_used=chunk_result.strategy_used,
                    # Domain metadata
                    vendor=chunk.vendor or None,
                    standard_id=chunk.standard_id or None,
                    doc_type=chunk.doc_type or None,
                    lang=chunk.lang or None,
                    block_types=chunk.block_types if chunk.block_types != ["normal"] else None,
                )
                db.add(db_chunk)

            await db.commit()

        await self.queue.complete(task.task_id)
        await self.queue.update_progress(
            task.task_id, 100, "Completed",
            {"chunks_created": total},
        )
        logger.info(
            "Task %s completed: %s → %d chunks",
            task.task_id, task.filename, total,
        )


# Global worker instance
_worker: DocumentWorker | None = None


async def start_worker():
    global _worker
    _worker = DocumentWorker()
    await _worker.start()


async def stop_worker():
    global _worker
    if _worker:
        await _worker.stop()
        _worker = None
