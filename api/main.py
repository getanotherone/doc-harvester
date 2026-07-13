import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from .auth import SCRAPPER_API_KEY, require_api_key
from .models import HealthResponse
from .routers import clean, crawl, discover, fetch, sources
from .tasks import registry

logger = logging.getLogger("scrapper.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not SCRAPPER_API_KEY:
        logger.warning(
            "SCRAPPER_API_KEY is not set — all authenticated endpoints will "
            "return 500. Set it via environment variable."
        )
    yield


app = FastAPI(
    title="Scrapper Microservice API",
    version="0.1.0",
    lifespan=lifespan,
)

# All routers require API key auth
auth = [Depends(require_api_key)]
app.include_router(discover.router, dependencies=auth)
app.include_router(sources.router, dependencies=auth)
app.include_router(crawl.router, dependencies=auth)
app.include_router(fetch.router, dependencies=auth)
app.include_router(clean.router, dependencies=auth)


# /health is open — no auth (Docker health checks, load balancers)
@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(
        status="ok",
        version="0.1.0",
        active_tasks=registry.active_count(),
    )
