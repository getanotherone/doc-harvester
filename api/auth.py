import os
import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key")

# Load from env; generate a random key if not set (logged on startup)
SCRAPPER_API_KEY = os.environ.get("SCRAPPER_API_KEY", "")


def require_api_key(key: str = Security(_api_key_header)) -> str:
    if not SCRAPPER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="SCRAPPER_API_KEY is not configured on the server",
        )
    if not secrets.compare_digest(key, SCRAPPER_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return key
