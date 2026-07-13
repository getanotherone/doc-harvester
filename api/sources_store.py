import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


class SourcesStore:
    """In-memory store hydrated from discovery JSON files.

    UUIDs are deterministic via uuid5(NAMESPACE_URL, url) — same URL always
    gets the same ID, surviving process restarts.
    """

    def __init__(self, candidates_path: Path, approved_path: Path):
        self._candidates_path = candidates_path
        self._approved_path = approved_path
        self._sources: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._reload()

    def _url_to_uuid(self, url: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, url))

    def _reload(self):
        sources: Dict[str, dict] = {}

        # Load candidates
        try:
            data = json.loads(self._candidates_path.read_text(encoding="utf-8"))
            for item in data.get("candidates", []):
                url = item.get("url", "")
                if not url:
                    continue
                uid = self._url_to_uuid(url)
                sources[uid] = {
                    "id": uid,
                    "url": url,
                    "domain": item.get("domain", ""),
                    "score": float(item.get("score", 0)),
                    "status": "candidate",
                    "mode": item.get("mode", "unknown"),
                    "profile": item.get("profile"),
                    "file_links_found": item.get("file_links_found"),
                    "product_links_found": item.get("product_links_found"),
                }
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        # Load approved — overrides status for matching URLs
        try:
            data = json.loads(self._approved_path.read_text(encoding="utf-8"))
            profile = data.get("profile")
            for item in data.get("sources", []):
                url = item.get("url", "")
                if not url:
                    continue
                uid = self._url_to_uuid(url)
                approved_flag = item.get("approved", False)
                rejected_flag = item.get("rejected", False)
                if approved_flag:
                    status = "approved"
                elif rejected_flag:
                    status = "rejected"
                else:
                    status = "candidate"
                existing = sources.get(
                    uid,
                    {
                        "id": uid,
                        "url": url,
                        "domain": item.get("domain", ""),
                        "score": float(item.get("score", 0)),
                        "mode": item.get("mode", "unknown"),
                    },
                )
                existing["status"] = status
                existing["profile"] = existing.get("profile") or profile
                sources[uid] = existing
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        with self._lock:
            self._sources = sources

    def list_sources(
        self,
        status_filter: Optional[str] = None,
        profile_filter: Optional[str] = None,
    ) -> List[dict]:
        with self._lock:
            result = list(self._sources.values())
        if status_filter:
            result = [s for s in result if s.get("status") == status_filter]
        if profile_filter:
            result = [s for s in result if s.get("profile") == profile_filter]
        return result

    def get(self, source_id: str) -> Optional[dict]:
        with self._lock:
            return self._sources.get(source_id)

    def set_status(self, source_id: str, new_status: str) -> Optional[dict]:
        with self._lock:
            source = self._sources.get(source_id)
            if not source:
                return None
            source = source.copy()
            source["status"] = new_status
            self._sources[source_id] = source

        self._persist_approved()
        return source

    def ingest_discovery_result(self, candidates: List[dict], profile: str):
        with self._lock:
            for item in candidates:
                url = item.get("url", "")
                if not url:
                    continue
                uid = self._url_to_uuid(url)
                existing = self._sources.get(uid)
                if existing and existing.get("status") in ("approved", "rejected"):
                    continue
                self._sources[uid] = {
                    "id": uid,
                    "url": url,
                    "domain": item.get("domain", ""),
                    "score": float(item.get("score", 0)),
                    "status": (
                        existing.get("status", "candidate") if existing else "candidate"
                    ),
                    "mode": item.get("mode", "unknown"),
                    "profile": profile,
                    "file_links_found": item.get("file_links_found"),
                    "product_links_found": item.get("product_links_found"),
                }
        self._persist_approved()

    def _persist_approved(self):
        with self._lock:
            all_sources = list(self._sources.values())

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Managed by API. Set approved=true/false for human review.",
            "sources": [
                {
                    "url": s["url"],
                    "domain": s.get("domain", ""),
                    "mode": s.get("mode", "unknown"),
                    "approved": s["status"] == "approved",
                    "rejected": s["status"] == "rejected",
                    "priority": idx + 1,
                    "score": s.get("score", 0),
                }
                for idx, s in enumerate(
                    sorted(all_sources, key=lambda x: -x.get("score", 0))
                )
            ],
        }
        self._approved_path.parent.mkdir(parents=True, exist_ok=True)
        self._approved_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


_project_root = Path(__file__).parent.parent
sources_store = SourcesStore(
    candidates_path=_project_root / "data" / "sources_candidates.json",
    approved_path=_project_root / "data" / "sources_approved.json",
)
