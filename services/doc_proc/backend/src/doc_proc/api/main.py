"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from doc_proc.queue.worker import start_worker, stop_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage worker lifecycle."""
    await start_worker()
    yield
    await stop_worker()


app = FastAPI(
    title="DocProc",
    description="Document Processing Microservice — parsing, chunking, embedding, evaluation",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers
from doc_proc.api.routers import (  # noqa: E402
    chunks,
    documents,
    methodology,
    pipeline,
    queue,
    stage3,
)

app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(chunks.router, prefix="/api/v1/chunks", tags=["Chunks"])
app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["Pipeline"])
app.include_router(methodology.router, prefix="/api/v1/methodologies", tags=["Methodologies"])
app.include_router(queue.router, prefix="/api/v1/queue", tags=["Queue"])
app.include_router(stage3.router, prefix="/api/v1/stage3", tags=["Stage3"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "doc-proc", "version": "0.1.0"}
