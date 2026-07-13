from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    accepted = "accepted"
    running = "running"
    completed = "completed"
    failed = "failed"


class SourceStatus(str, Enum):
    candidate = "candidate"
    approved = "approved"
    rejected = "rejected"


class SourceMode(str, Enum):
    web = "web"
    files = "files"
    unknown = "unknown"


class Progress(BaseModel):
    processed: int = 0
    total: int = 0


# --- Health ---


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    active_tasks: int = 0


# --- Task ---


class TaskCreated(BaseModel):
    task_id: UUID
    status: str = "accepted"


# --- Discovery ---


class DiscoverRequest(BaseModel):
    profile: str
    engine: str = "yandex"
    top_n: int = 30
    probe: bool = False


class DiscoverStatus(BaseModel):
    task_id: UUID
    status: TaskStatus
    progress: Optional[Progress] = None
    candidates_found: Optional[int] = None
    error: Optional[str] = None


# --- Sources ---


class Source(BaseModel):
    id: UUID
    url: str
    domain: str
    score: float = 0.0
    status: SourceStatus = SourceStatus.candidate
    mode: SourceMode = SourceMode.unknown
    profile: Optional[str] = None
    probed_at: Optional[datetime] = None
    file_links_found: Optional[int] = None
    product_links_found: Optional[int] = None


class SourcesList(BaseModel):
    sources: List[Source]
    total: int


class ApproveRequest(BaseModel):
    status: str


# --- Crawl ---


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 500
    mode: str = "auto"
    delay_sec: float = 1.0
    callback_url: Optional[str] = None


class CrawlStatus(BaseModel):
    task_id: UUID
    status: TaskStatus
    progress: Optional[Progress] = None
    pages_visited: Optional[int] = None
    product_urls_found: Optional[int] = None
    file_urls_found: Optional[int] = None
    errors: Optional[int] = None
    rate_limits: Optional[int] = None
    started_at: Optional[datetime] = None
    eta_sec: Optional[int] = None
    error: Optional[str] = None


# --- Fetch ---


class FetchRequest(BaseModel):
    urls: List[str] = Field(..., max_length=500)
    mode: str = "auto"
    delay_sec: float = 1.0
    callback_url: Optional[str] = None


class FetchResult(BaseModel):
    url: str
    status: str
    content_type: Optional[str] = None
    file_path: Optional[str] = None
    cleaned_html: Optional[str] = None
    size_bytes: Optional[int] = None
    error: Optional[str] = None


class FetchResults(BaseModel):
    task_id: UUID
    status: TaskStatus
    progress: Optional[Progress] = None
    results: List[FetchResult] = []


# --- Clean HTML ---


class CleanHtmlRequest(BaseModel):
    html: str
    url: Optional[str] = None


class CleanHtmlResponse(BaseModel):
    cleaned_html: str
    removed_elements: int
    original_size: int
    cleaned_size: int
