"""Validated discovery profiles used by the public CLI and discovery API."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


class ProfileValidationError(ValueError):
    """Raised when a discovery profile does not match the public schema."""


_PROFILE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_CRAWL_FIELDS: dict[str, type] = {
    "max_pages": int,
    "file_score_threshold": int,
    "follow_child_score_threshold": int,
    "web_min_product_score": int,
    "relevance_filter": bool,
}


def _string_list(payload: Mapping[str, Any], key: str, *, required: bool) -> tuple[str, ...]:
    value = payload.get(key)
    if value is None and not required:
        return ()
    if not isinstance(value, list):
        raise ProfileValidationError(f"'{key}' must be an array of strings")
    cleaned: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ProfileValidationError(f"'{key}[{index}]' must be a non-empty string")
        cleaned.append(item.strip())
    if required and not cleaned:
        raise ProfileValidationError(f"'{key}' must contain at least one item")
    return tuple(cleaned)


def _crawl_settings(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProfileValidationError("'crawl' must be an object")
    unknown = sorted(set(value) - set(_CRAWL_FIELDS))
    if unknown:
        raise ProfileValidationError(f"unknown crawl fields: {', '.join(unknown)}")
    result: dict[str, Any] = {}
    for key, item in value.items():
        expected = _CRAWL_FIELDS[key]
        if expected is int and (not isinstance(item, int) or isinstance(item, bool)):
            raise ProfileValidationError(f"'crawl.{key}' must be an integer")
        if expected is bool and not isinstance(item, bool):
            raise ProfileValidationError(f"'crawl.{key}' must be a boolean")
        if key == "max_pages" and item < 1:
            raise ProfileValidationError("'crawl.max_pages' must be at least 1")
        result[key] = item
    return result


@dataclass(frozen=True)
class DiscoveryProfile:
    """Portable, validated discovery configuration."""

    name: str
    queries: tuple[str, ...]
    priority_terms: tuple[str, ...] = ()
    priority_domains: tuple[str, ...] = ()
    crawl: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    @classmethod
    def from_dict(cls, name: str, payload: Mapping[str, Any]) -> "DiscoveryProfile":
        if not _PROFILE_NAME.fullmatch(name):
            raise ProfileValidationError(
                "profile name must contain only lowercase letters, numbers, '-' and '_'"
            )
        if not isinstance(payload, Mapping):
            raise ProfileValidationError("profile must be a JSON object")
        allowed = {
            "schema_version",
            "queries",
            "priority_terms",
            "priority_domains",
            "crawl",
            "metadata",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ProfileValidationError(f"unknown profile fields: {', '.join(unknown)}")
        version = payload.get("schema_version", 1)
        if version != 1:
            raise ProfileValidationError("'schema_version' must be 1")
        crawl = payload.get("crawl", {})
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ProfileValidationError("'metadata' must be an object")
        return cls(
            name=name,
            queries=_string_list(payload, "queries", required=True),
            priority_terms=_string_list(payload, "priority_terms", required=False),
            priority_domains=_string_list(payload, "priority_domains", required=False),
            crawl=_crawl_settings(crawl),
            metadata=dict(metadata),
            schema_version=version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "queries": list(self.queries),
            "priority_terms": list(self.priority_terms),
            "priority_domains": list(self.priority_domains),
            "crawl": dict(self.crawl),
            "metadata": dict(self.metadata),
        }


def load_profile(path_or_name: str | Path, profiles_dir: str | Path = "config/profiles") -> DiscoveryProfile:
    """Load a profile by JSON path or by name from ``profiles_dir``."""
    requested = Path(path_or_name)
    if requested.suffix.lower() == ".json" or requested.parent != Path("."):
        path = requested
        name = path.stem
    else:
        name = str(path_or_name)
        if not _PROFILE_NAME.fullmatch(name):
            raise ProfileValidationError(f"invalid profile name: {name!r}")
        path = Path(profiles_dir) / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"profile not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ProfileValidationError(f"invalid JSON in {path}: {error}") from error
    return DiscoveryProfile.from_dict(name, payload)


def list_profiles(profiles_dir: str | Path = "config/profiles") -> list[str]:
    directory = Path(profiles_dir)
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json") if _PROFILE_NAME.fullmatch(path.stem))
