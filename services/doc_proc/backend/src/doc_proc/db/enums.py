"""Database enums."""

import enum


class DocumentStatus(str, enum.Enum):  # noqa: UP042
    uploaded = "uploaded"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ChunkType(str, enum.Enum):  # noqa: UP042
    text = "text"
    table = "table"
    heading = "heading"
    list = "list"
    image = "image"
    normative = "normative"


class SourceType(str, enum.Enum):  # noqa: UP042
    upload = "upload"
    text = "text"
    url = "url"


class QueueTaskStatus(str, enum.Enum):  # noqa: UP042
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    retrying = "retrying"
