from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / ".env.example"


def _active_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        assert separator, f"invalid .env.example line: {raw_line}"
        assert key not in values, f"duplicate .env.example key: {key}"
        values[key] = value
    return values


def test_root_env_example_has_universal_safe_defaults():
    values = _active_values()

    assert values["DOC_HARVESTER_STORAGE"] == "local"
    assert values["DOC_HARVESTER_PUBLISHER"] == "local"
    assert values["UPLOAD_ENABLED"] == "0"
    assert values["SEARCH_DISCOVERY_ENABLED"] == "0"
    assert values["ELECTRICAL_ONLY"] == "0"
    assert "DOC_HARVESTER_PROFILE" not in values
    assert "change-me" not in EXAMPLE.read_text(encoding="utf-8")


def test_root_env_example_keeps_every_secret_blank():
    values = _active_values()
    secret_names = {
        "SCRAPPER_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "NOTION_TOKEN",
        "CONFLUENCE_EMAIL",
        "CONFLUENCE_API_TOKEN",
        "YANDEX_DISK_TOKEN",
        "YANDEX_SEARCH_API_KEY",
        "YANDEX_SEARCH_FOLDER_ID",
        "YANDEX_WIKI_TOKEN",
        "YANDEX_WIKI_CLOUD_ORG_ID",
    }

    assert secret_names <= values.keys()
    assert all(values[name] == "" for name in secret_names)


def test_root_env_example_covers_the_public_standalone_surface():
    documented_names = set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", EXAMPLE.read_text()))
    expected_names = {
        "DOC_HARVESTER_STORAGE",
        "DOC_HARVESTER_LOCAL_STORAGE_ROOT",
        "DOC_HARVESTER_PUBLISHER",
        "DOC_HARVESTER_PUBLISH_ROOT",
        "DOC_HARVESTER_PROFILE",
        "DOC_HARVESTER_DISCOVERY_LIMIT",
        "DOC_HARVESTER_MAX_SITEMAPS",
        "DOC_HARVESTER_MAX_SITEMAP_BYTES",
        "DOC_HARVESTER_FETCH_ROOT",
        "DOC_HARVESTER_MAX_FETCH_BYTES",
        "DOC_HARVESTER_HTTP_TIMEOUT",
        "DOC_HARVESTER_MAX_MANIFEST_BYTES",
        "DOC_HARVESTER_MAX_CHUNK_TOKENS",
        "SCRAPPER_API_KEY",
        "S3_BUCKET",
        "NOTION_TOKEN",
        "CONFLUENCE_API_TOKEN",
        "YANDEX_DISK_TOKEN",
        "YANDEX_SEARCH_API_KEY",
        "WEB_CRAWL_DELAY_SEC",
        "QUALITY_MIN_TOKENS",
        "BROWSER_TIMEOUT_MS",
        "DOCPROC_URL",
    }

    assert expected_names <= documented_names


def test_root_env_example_does_not_duplicate_docproc_service_configuration():
    values = _active_values()

    assert "DATABASE_URL" not in values
    assert "REDIS_URL" not in values
    assert "MINIO_ENDPOINT" not in values
    assert "EMBEDDING_PROVIDER" not in values
