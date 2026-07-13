"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Database
    database_url: str = "postgresql+asyncpg://doc_proc:doc_proc@postgres:5432/doc_proc"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "documents"
    minio_secure: bool = False

    # Embedding
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    embedding_dimension: int = 1024
    embedding_base_url: str = "http://host.docker.internal:11434"
    embedding_api_key: str = ""
    embedding_batch_size: int = 64
    embedding_concurrency: int = 1
    embedding_timeout: float = 180.0
    embedding_max_retries: int = 3

    # Parsing
    max_upload_size_mb: int = 500
    max_pdf_ocr_size_mb: int = 50
    ocr_engine: str = "tesseract"
    ocr_languages: str = "rus+eng"
    docling_table_mode: str = "fast"
    docling_images_scale: float = 0.75
    docling_ocr_batch_size: int = 2
    docling_layout_batch_size: int = 2
    docling_table_batch_size: int = 2

    # Worker
    worker_max_concurrent: int = 1
    worker_max_chunks: int = 50000
    max_excel_cells: int = 2_000_000


settings = Settings()
