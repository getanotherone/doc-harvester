import csv
import fcntl
import json
import os
import re
import shutil
import tempfile
import time
from datetime import date, datetime
from typing import Any, Dict, List
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from chunker import chunk_units_v2
from extractors import extract_html_string_to_units
from pdf_extractor_v2 import download_pdf_from_yandex
from quality_eval import evaluate_quality_for_document


def _yandex():
    """Lazy import of yandex module — avoids RuntimeError when YANDEX_DISK_TOKEN is not set."""
    import yandex
    return yandex


def _storage():
    """Create the configured storage adapter at the upload boundary."""
    from doc_harvester.storage import create_storage

    return create_storage(STORAGE_PROVIDER)


def configure_profile(profile: Any) -> None:
    """Apply a validated discovery profile to legacy crawler globals."""
    global DOMAIN, ELECTRICAL_TERMS, ELECTRICAL_ONLY
    global CRAWL_MAX_PAGES_PER_SOURCE, ELECTRICAL_SCORE_THRESHOLD
    global FOLLOW_CHILD_SCORE_THRESHOLD, WEB_MIN_PRODUCT_SCORE

    DOMAIN = str(profile.metadata.get("domain") or profile.name)
    ELECTRICAL_TERMS = tuple(profile.priority_terms)
    settings = profile.crawl
    ELECTRICAL_ONLY = settings.get("relevance_filter", bool(ELECTRICAL_TERMS))
    CRAWL_MAX_PAGES_PER_SOURCE = settings.get("max_pages", CRAWL_MAX_PAGES_PER_SOURCE)
    ELECTRICAL_SCORE_THRESHOLD = settings.get(
        "file_score_threshold", ELECTRICAL_SCORE_THRESHOLD
    )
    FOLLOW_CHILD_SCORE_THRESHOLD = settings.get(
        "follow_child_score_threshold", FOLLOW_CHILD_SCORE_THRESHOLD
    )
    WEB_MIN_PRODUCT_SCORE = settings.get("web_min_product_score", WEB_MIN_PRODUCT_SCORE)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

ALLOWED_EXT = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".html", ".htm", ".xml")
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(_PROJECT_ROOT, "data", "state.json")
HASH_INDEX_FILE = os.path.join(_PROJECT_ROOT, "data", "hash_index.json")
DEAD_URLS_FILE = os.path.join(_PROJECT_ROOT, "data", "dead_urls.json")
CONSECUTIVE_404_THRESHOLD = int(os.environ.get("CONSECUTIVE_404_THRESHOLD", "20"))  # 0 = disabled
METADATA_FILE = os.path.join(_PROJECT_ROOT, "data", "metadata.csv")
LOCAL_DATASET_ROOT = os.path.join(_PROJECT_ROOT, "datasets")
RUNS_DIR = os.path.join(_PROJECT_ROOT, "runs")
DOMAIN = "electrical"
APPROVED_SOURCES_FILE = os.path.join(_PROJECT_ROOT, "data", "sources_approved.json")

CHUNK_TARGET_TOKENS = 1000
CHUNK_MAX_TOKENS = 1200
CRAWL_CHILD_PAGES = os.environ.get("CRAWL_CHILD_PAGES", "1").lower() not in ("0", "false", "no")
CRAWL_MAX_PAGES_PER_SOURCE = int(os.environ.get("CRAWL_MAX_PAGES_PER_SOURCE", "120"))
ELECTRICAL_ONLY = os.environ.get("ELECTRICAL_ONLY", "1").lower() not in ("0", "false", "no")
ELECTRICAL_SCORE_THRESHOLD = int(os.environ.get("ELECTRICAL_SCORE_THRESHOLD", "2"))
FOLLOW_CHILD_SCORE_THRESHOLD = int(os.environ.get("FOLLOW_CHILD_SCORE_THRESHOLD", "0"))
QUALITY_GATE_BLOCK_WARN = os.environ.get("QUALITY_GATE_BLOCK_WARN", "1").lower() not in (
    "0",
    "false",
    "no",
)
QUARANTINE_SUBDIR = os.environ.get("QUARANTINE_SUBDIR", "_quarantine").strip("/") or "_quarantine"
WEB_CRAWL_DELAY_SEC = float(os.environ.get("WEB_CRAWL_DELAY_SEC", "5.0"))
WEB_MIN_CONTENT_BLOCKS = int(os.environ.get("WEB_MIN_CONTENT_BLOCKS", "3"))
WEB_MIN_PRODUCT_SCORE = int(os.environ.get("WEB_MIN_PRODUCT_SCORE", "2"))
SITEMAP_ENABLED = os.environ.get("SITEMAP_ENABLED", "1").lower() not in ("0", "false", "no")
SEARCH_DISCOVERY_ENABLED = os.environ.get("SEARCH_DISCOVERY_ENABLED", "1").lower() not in (
    "0", "false", "no"
)
SEARCH_MAX_QUERIES_PER_SOURCE = int(os.environ.get("SEARCH_MAX_QUERIES_PER_SOURCE", "50"))
UPLOAD_ENABLED = os.environ.get("UPLOAD_ENABLED", "1").lower() not in ("0", "false", "no")
STORAGE_PROVIDER = os.environ.get("DOC_HARVESTER_STORAGE", "local").strip().lower()
BFS_ENABLED = os.environ.get("BFS_ENABLED", "1").lower() not in ("0", "false", "no")

# URL path segments that indicate non-product pages (commercial/operational)
_SKIP_URL_SEGMENTS = re.compile(
    r"/(delivery|dostavka|shipping|payment|oplata|payments|order|zakaz|cart|korzina"
    r"|checkout|login|register|auth|account|profile|contacts|kontakty|about"
    r"|o-nas|o-kompanii|company|vakansii|careers|news|novosti|blog|faq|help"
    r"|support|sitemap|privacy|policy|terms|agreement|offer|oferta|return"
    r"|vozvrat|garantiya|guarantee|warranty|reviews|otzyvy|partners|partnery|reklama"
    r"|advertising|subscribe|podpiska|compare|sravnenie|wishlist|favorites"
    r"|izbranno|leasing|lizzing|insurance|strahovanie|financial|finansy"
    r"|requisites|rekvizity|feedback|obratna|filter__[^/]*)"
    r"(\.[a-z]{2,5})?(/|$|\?)",
    re.IGNORECASE,
)

# Terms that indicate technical product/spec content
PRODUCT_SPEC_TERMS = (
    # Measurement units
    "мм²", "мм2", "мм ", "кв.мм", "кв.м", " мм", " см", " м ",
    " в ", " а ", " ка ", " ква", " квт", " квар", " вт ", " ом ",
    "°c", "°с", "кг/км", "кг/м",
    # Technical attributes
    "сечени", "напряжени", "характеристик", "параметр", "конструкци",
    "температур", "сопротивлен", "изоляци", "оболочк", "жил",
    "номинальн", "допустим", "ток ", "мощност", "диаметр",
    "масса", "вес ", "длин", "радиус", "толщин",
    "марк", "модификац", "типоразмер", "артикул", "модел",
    # Product structure
    "технические данные", "техническое описание", "спецификаци",
    "применени", "назначени", "область применения",
    "расшифровка", "маркировк", "обозначени",
    # Standards
    "гост", "ту ", "iec", "iso",
)

# Anti-terms for product scoring — indicate commercial/operational pages
PRODUCT_ANTI_TERMS = (
    # Commercial/ordering
    "доставк", "оплат", "способ оплаты", "корзин", "заказ ",
    "оформить заказ", "купить", "в корзину", "добавить в",
    "возврат", "гарантийн", "рекламац", "политика конфиденциальности",
    "пользовательское соглашение", "подписаться", "рассылк",
    "вакансии", "карьера", "партнерская программа",
    # Editorial/journalism signals
    "интервью", "корреспондент", "журналист", "редакция",
    "обзор рынка", "аналитический обзор", "подробнее читайте",
    "продолжение следует", "по мнению эксперт",
)

ELECTRICAL_TERMS = (
    "электр",
    "электрика",
    "электротехничес",
    "кабель",
    "провод",
    "автомат",
    "узо",
    "дифавтомат",
    "контактор",
    "реле",
    "выключател",
    "щит",
    "щитов",
    "нку",
    "низковольт",
    "распредел",
    "transformer",
    "switchgear",
    "electric",
    "electro",
    "cable",
    "breaker",
    "legrand",
    "schneider",
    "abb",
    "iek",
    "ekf",
    "hager",
    "гост",
    "гост р",
    "сп",
    "снип",
    "пэу",
    "пуэ",
    "фз",
    "тр",
    "техническ",
    "норматив",
    "стандарт",
    "регламент",
    "электроустанов",
    "электроснаб",
    "электромонтаж",
    "кабельн",
    "трансформатор",
    "распредщит",
    "низковольтн",
    "высоковольтн",
    "electrical",
    "electrotechn",
    "iec",
    "gost",
)

ANTI_TERMS = (
    "fashion",
    "casino",
    "game",
    "play.google",
    "youtube",
    "instagram",
)


def get_domain_name(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def sanitize_domain(domain: str) -> str:
    return domain.replace(":", "_")


def load_json(path: str, default: Any) -> Any:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    return default


def _atomic_write_json(path: str, data: Any) -> None:
    """Write JSON to a same-dir temp file, then atomically rename onto `path`.

    Cleans the temp file on any failure (including KeyboardInterrupt) so an
    interrupted write doesn't leave behind `<name>.tmp.<pid>` garbage that
    accumulates over many overnight crawl runs.
    """
    dir_name = os.path.dirname(path) or "."
    base = os.path.basename(path)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{base}.tmp.", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


def save_json(path: str, data: Any) -> None:
    _atomic_write_json(path, data)


def save_state_json(path: str, processed: set) -> None:
    """Save state.json with file locking to prevent corruption from parallel crawlers.

    Multiple crawlers run at the same time and all share state.json.  Without
    a lock, crawler A can overwrite crawler B's newly-added URLs.  This function:
    1. Acquires an exclusive lock on a .lock file (blocks until other writers finish)
    2. Re-reads the current file (picks up other crawlers' writes)
    3. Merges in our URLs
    4. Writes atomically (tmp + rename)
    5. Releases the lock
    """
    lock_path = path + ".lock"
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)  # wait for exclusive access
        # Re-read: another crawler may have written since we last loaded
        on_disk = set(load_json(path, []))
        merged = on_disk | processed  # union — never lose URLs
        _atomic_write_json(path, sorted(merged))
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def save_dict_json_locked(path: str, data: dict) -> None:
    """Like save_state_json but for dict files (hash_index.json, dead_urls.json).

    Merges our dict into whatever is on disk, so parallel crawlers don't
    overwrite each other's entries.
    """
    lock_path = path + ".lock"
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        default = [] if isinstance(data, list) else {}
        on_disk = load_json(path, default)
        if isinstance(data, list):
            # dead_urls.json is a sorted list — merge as sets
            merged = sorted(set(on_disk if isinstance(on_disk, list) else []) | set(data))
        else:
            # hash_index.json is a dict — our values win on conflict (newer)
            merged = {**(on_disk if isinstance(on_disk, dict) else {}), **data}
        _atomic_write_json(path, merged)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def retry(func, attempts: int = 3, delay_sec: float = 1.5):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as error:  # noqa: PERF203
            last_error = error
            if attempt == attempts:
                break
            sleep_for = delay_sec * attempt
            print(f"Retry {attempt}/{attempts} after error: {error}")
            time.sleep(sleep_for)
    raise last_error


_metadata_keys: set = set()  # (source_domain, filename) pairs already in CSV


def _load_metadata_keys() -> None:
    """Load existing (source_domain, filename) pairs for dedup."""
    if _metadata_keys:
        return
    if not os.path.exists(METADATA_FILE):
        return
    with open(METADATA_FILE, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            _metadata_keys.add((row["source_domain"], row["filename"]))


def append_metadata(row: Dict[str, str]) -> None:
    _load_metadata_keys()
    key = (row["source_domain"], row["filename"])
    if key in _metadata_keys:
        return  # skip duplicate

    file_exists = os.path.exists(METADATA_FILE)

    with open(METADATA_FILE, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(
            csvfile,
            fieldnames=[
                "source_domain",
                "ingest_date",
                "filename",
                "source_url",
                "disk_path",
                "sha256",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
    _metadata_keys.add(key)


def electrical_score(text: str) -> int:
    lower = (text or "").lower()
    score = 0
    for term in ELECTRICAL_TERMS:
        if term in lower:
            score += 1
    for term in ANTI_TERMS:
        if term in lower:
            score -= 2
    return score


def _is_file_link(url: str) -> bool:
    lower = url.lower()
    return any(lower.endswith(ext) or f"{ext}?" in lower for ext in ALLOWED_EXT)


def _get_url_ext(url: str) -> str:
    path = urlparse(url).path.lower()
    _, ext = os.path.splitext(path)
    return ext


def _normalize_http_url(base_url: str, href: str) -> str:
    absolute = urljoin(base_url, href.strip())
    clean, _ = urldefrag(absolute)
    return clean


def _is_same_domain(url_a: str, url_b: str) -> bool:
    return get_domain_name(url_a) == get_domain_name(url_b)


def _should_follow_child(root_url: str, candidate_url: str, anchor_text: str) -> bool:
    if not _is_same_domain(root_url, candidate_url):
        return False

    parsed_root = urlparse(root_url)
    parsed_candidate = urlparse(candidate_url)

    if parsed_candidate.scheme not in ("http", "https"):
        return False
    if parsed_candidate.path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xml")):
        return False

    root_prefix = parsed_root.path.rstrip("/")
    if root_prefix and parsed_candidate.path.startswith(root_prefix):
        return True

    if not ELECTRICAL_ONLY:
        return True

    relevance = electrical_score(f"{candidate_url} {anchor_text}")
    return relevance >= FOLLOW_CHILD_SCORE_THRESHOLD


def extract_links(page_url: str) -> List[str]:
    if page_url.lower().endswith(ALLOWED_EXT):
        return [page_url]

    to_visit = [page_url]
    visited_pages = set()
    file_links: Dict[str, str] = {}

    while to_visit and len(visited_pages) < CRAWL_MAX_PAGES_PER_SOURCE:
        current = to_visit.pop(0)
        if current in visited_pages:
            continue
        visited_pages.add(current)

        try:
            response = retry(
                lambda: requests.get(current, headers=REQUEST_HEADERS, timeout=30)
            )
            response.raise_for_status()
            html = response.text
        except Exception as error:
            print(f"SKIP page crawl failed: {current} -> {error}")
            continue

        soup = BeautifulSoup(html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            anchor_text = a_tag.get_text(" ", strip=True)
            absolute_url = _normalize_http_url(current, href)
            if not absolute_url.startswith(("http://", "https://")):
                continue

            if _is_file_link(absolute_url):
                existing = file_links.get(absolute_url, "")
                file_links[absolute_url] = f"{existing} {anchor_text}".strip()
                continue

            if CRAWL_CHILD_PAGES and _should_follow_child(page_url, absolute_url, anchor_text):
                if absolute_url not in visited_pages:
                    to_visit.append(absolute_url)

        allowed_pattern = "|".join(ext.lstrip(".") for ext in ALLOWED_EXT)
        file_url_pattern = rf"https?://[^\s\"'<>]+\.(?:{allowed_pattern})(?:\?[^\s\"'<>]*)?"
        for full_url in re.findall(file_url_pattern, html, re.IGNORECASE):
            file_links.setdefault(full_url, "")

    result = []
    maybe_kept = 0
    dropped = 0
    weak_ext_allow = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xml", ".html", ".htm"}

    for url in sorted(file_links.keys()):
        if not ELECTRICAL_ONLY:
            result.append(url)
            continue
        score = electrical_score(f"{url} {file_links.get(url, '')}")
        if score >= ELECTRICAL_SCORE_THRESHOLD:
            result.append(url)
            continue

        ext = _get_url_ext(url)
        if score >= 0 and ext in weak_ext_allow:
            result.append(url)
            maybe_kept += 1
            continue

        dropped += 1

    print(
        f"Crawl summary for {page_url}: pages={len(visited_pages)}, "
        f"file_candidates={len(file_links)}, kept={len(result)}, "
        f"maybe_kept={maybe_kept}, dropped={dropped}"
    )
    return result


def download_to_temp_file(url: str, filename: str) -> str:
    temp_dir = "/tmp/doc_harvester_ingest"
    os.makedirs(temp_dir, exist_ok=True)
    local_path = os.path.join(temp_dir, filename)
    retry(lambda: download_pdf_from_yandex(url, local_path))
    return local_path


def write_run_manifest(manifest: Dict[str, Any]) -> str:
    os.makedirs(RUNS_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(RUNS_DIR, f"ingest_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)
    return out_path



def load_approved_sources(path: str = APPROVED_SOURCES_FILE) -> List[str]:
    """Load approved sources from discovery review file."""
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as error:
        print(f"WARNING: failed to read {path}: {error}")
        return []

    sources = payload.get("sources", [])
    approved_items = [item for item in sources if item.get("approved") is True]
    approved_items.sort(key=lambda item: int(item.get("priority", 999999)))

    approved_urls = []
    for item in approved_items:
        url = str(item.get("url", "")).strip()
        if url and url.startswith(("http://", "https://")):
            approved_urls.append(url)

    return approved_urls



def ingest_page(page_url: str, disk_folder: str) -> Dict[str, Any]:
    storage = _storage() if UPLOAD_ENABLED else None

    processed = set(load_json(STATE_FILE, []))
    hash_index = load_json(HASH_INDEX_FILE, {})

    links = extract_links(page_url)

    source_domain = sanitize_domain(get_domain_name(page_url))
    ingest_date = date.today().isoformat()

    print(f"Found {len(links)} files")

    manifest: Dict[str, Any] = {
        "source_page": page_url,
        "source_domain": source_domain,
        "started_at": datetime.utcnow().isoformat(),
        "links_found": len(links),
        "documents": [],
    }

    for link in links:
        filename = link.split("/")[-1].split("?")[0]
        ext = os.path.splitext(filename.lower())[1]
        disk_path = f"{disk_folder}/{filename}"

        doc_result: Dict[str, Any] = {
            "source_url": link,
            "filename": filename,
            "extension": ext,
            "disk_path": disk_path,
            "status": "started",
            "started_at": datetime.utcnow().isoformat(),
        }

        manifest["documents"].append(doc_result)

        if link in processed:
            doc_result["status"] = "skipped_processed"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            print(f"SKIP (processed): {link}")
            continue

        if storage and storage.exists(disk_path):
            doc_result["status"] = "skipped_exists_on_disk"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            print(f"SKIP (exists on disk): {filename}")
            processed.add(link)
            save_state_json(STATE_FILE, processed)
            continue

        local_path = None

        try:
            import hashlib as _hashlib

            local_path = download_to_temp_file(link, filename)

            # Compute hash locally
            with open(local_path, "rb") as _f:
                file_hash = _hashlib.sha256(_f.read()).hexdigest()

            if file_hash in hash_index:
                print(f"DUPLICATE: {filename}")
                doc_result["status"] = "duplicate"
                doc_result["sha256"] = file_hash
                doc_result["finished_at"] = datetime.utcnow().isoformat()
                if local_path and os.path.exists(local_path):
                    os.remove(local_path)
                continue

            # Keep file locally for batch upload later
            local_store = os.path.join(LOCAL_DATASET_ROOT, DOMAIN, source_domain, "files")
            os.makedirs(local_store, exist_ok=True)
            stored_path = os.path.join(local_store, filename)
            os.replace(local_path, stored_path)
            local_path = stored_path

            if storage:
                retry(lambda: storage.put_file(local_path, disk_path))
                time.sleep(1)

            hash_index[file_hash] = disk_path
            save_dict_json_locked(HASH_INDEX_FILE, hash_index)

            append_metadata(
                {
                    "source_domain": source_domain,
                    "ingest_date": ingest_date,
                    "filename": filename,
                    "source_url": link,
                    "disk_path": disk_path,
                    "sha256": file_hash,
                }
            )

            doc_result["status"] = "ingested"
            doc_result["sha256"] = file_hash
            doc_result["finished_at"] = datetime.utcnow().isoformat()

            processed.add(link)
            save_state_json(STATE_FILE, processed)
            print(f"INGESTED: {filename}")

        except Exception as error:
            doc_result["status"] = "failed"
            doc_result["error"] = str(error)
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            print(f"FAILED: {filename} -> {error}")

        finally:
            # Clean up temp file if it wasn't moved to local store
            temp_dir = "/tmp/doc_harvester_ingest"
            if local_path and os.path.exists(local_path) and local_path.startswith(temp_dir):
                os.remove(local_path)

    manifest["finished_at"] = datetime.utcnow().isoformat()

    status_counts: Dict[str, int] = {}
    for item in manifest["documents"]:
        key = item.get("status", "unknown")
        status_counts[key] = status_counts.get(key, 0) + 1
    manifest["status_counts"] = status_counts

    manifest_path = write_run_manifest(manifest)
    print(f"Run manifest: {manifest_path}")

    return manifest


def _url_to_document_id(root_url: str, page_url: str) -> str:
    """Convert URL path to a safe document_id relative to root."""
    parsed = urlparse(page_url)
    path = parsed.path.strip("/")
    # Remove common extensions
    for ext in (".php", ".html", ".htm", ".asp", ".aspx", ".jsp"):
        if path.lower().endswith(ext):
            path = path[: -len(ext)]
            break
    # Remove root URL prefix if under root, otherwise use full path
    root_path = urlparse(root_url).path.strip("/")
    if root_path and path.startswith(root_path):
        path = path[len(root_path) :].strip("/")
    # Replace path separators with double underscore
    doc_id = path.replace("/", "__") if path else "index"
    # Sanitize: keep only safe characters
    doc_id = re.sub(r"[^\w\-]", "_", doc_id).strip("_") or "index"
    # macOS HFS+/APFS has 255-byte filename limit; truncate and append hash
    if len(doc_id.encode("utf-8")) > 200:
        import hashlib
        suffix = hashlib.sha1(doc_id.encode()).hexdigest()[:12]
        # Truncate to 200 bytes then trim to last underscore for clean cut
        truncated = doc_id.encode("utf-8")[:187].decode("utf-8", errors="ignore")
        last_sep = truncated.rfind("_")
        if last_sep > 100:
            truncated = truncated[:last_sep]
        doc_id = f"{truncated}_{suffix}"
    return doc_id


_SKIP_MEDIA_PATHS = re.compile(
    r"/(upload|medialibrary|bitrix|assets|static|images|img|media|fonts|css|js)/",
    re.IGNORECASE,
)

_MEDIA_EXTENSIONS = re.compile(
    r"\.(png|jpg|jpeg|gif|svg|webp|ico|mp4|mp3|wav|woff2?|ttf|eot|css|js)(\?|$)",
    re.IGNORECASE,
)


def _is_product_url(url: str) -> bool:
    """Return False if the URL path matches known non-product patterns."""
    path = urlparse(url).path
    if _SKIP_URL_SEGMENTS.search(path):
        return False
    if _SKIP_MEDIA_PATHS.search(path):
        return False
    if _MEDIA_EXTENSIONS.search(path):
        return False
    return True


def product_spec_score(text: str, url: str = "") -> int:
    """Score text for product/technical specification content.

    Uses term density (hits per 1000 chars) so long editorial articles
    with a few stray technical words don't outscore short spec cards.

    URL-path penalty: pages under /article/, /story/, /press/ start at -3
    because editorial content needs to clear a higher bar.
    """
    lower = (text or "").lower()
    raw_score = 0
    for term in PRODUCT_SPEC_TERMS:
        if term in lower:
            raw_score += 1
    for term in PRODUCT_ANTI_TERMS:
        if term in lower:
            raw_score -= 2

    # Density normalization: score per 1000 characters
    text_len = max(len(lower), 1)
    density_score = raw_score * 1000 / text_len

    # Convert back to integer scale: short spec pages keep their score,
    # long articles with sparse terms get penalized
    score = int(density_score * (min(text_len, 2000) / 1000))

    # URL-path penalty for editorial content paths
    if url:
        path = urlparse(url).path.lower()
        if re.search(r"/(article|story|press|blog|interview|obzor|analitika)/", path):
            score -= 3

    return score


class RateLimitError(Exception):
    """Raised when a site returns 429 after all retries — signals to abort the crawl."""
    pass


class CaptchaBlockedError(Exception):
    """Raised after consecutive CAPTCHA detections — session is expired, abort crawl."""
    pass


class FetchResult:
    """Result of a page fetch — distinguishes 404 from other failures."""
    __slots__ = ("html", "is_404", "rendered_text")

    def __init__(self, html: str | None, is_404: bool = False, rendered_text: str = ""):
        self.html = html
        self.is_404 = is_404
        self.rendered_text = rendered_text


def _fetch_page_html(url: str, spa_mode: bool = False) -> FetchResult:
    """Fetch page HTML via Playwright with retry and 429 backoff.

    Returns FetchResult with html on success, html=None on failure.
    FetchResult.is_404 is True when the server returned 404.
    When spa_mode=True, also captures rendered inner text for SPA extraction.
    Raises RateLimitError after 3 consecutive 429s — caller should abort.
    """
    from browser import browser_fetch, browser_fetch_rendered, _Rate429, _Http404, _CaptchaDetected

    captcha_consecutive = getattr(_fetch_page_html, "_captcha_consecutive", 0)

    for attempt in range(1, 4):
        try:
            if spa_mode:
                result = browser_fetch_rendered(url)
                if result is not None:
                    _fetch_page_html._captcha_consecutive = 0
                    return FetchResult(result.html, rendered_text=result.rendered_text)
                return FetchResult(None)
            else:
                html = browser_fetch(url)
                if html is not None:
                    _fetch_page_html._captcha_consecutive = 0
                    return FetchResult(html)
                return FetchResult(None)
        except _Http404:
            return FetchResult(None, is_404=True)
        except _CaptchaDetected as e:
            captcha_consecutive += 1
            _fetch_page_html._captcha_consecutive = captcha_consecutive
            print(f"  CAPTCHA detected on {url} ({captcha_consecutive} consecutive)")
            if captcha_consecutive >= 3:
                raise CaptchaBlockedError(
                    f"CAPTCHA on {captcha_consecutive} consecutive pages — session expired, aborting"
                )
            return FetchResult(None)
        except _Rate429:
            wait = min(30 * attempt, 90)
            print(f"  429 rate-limited on {url}, waiting {wait}s (attempt {attempt}/3)")
            time.sleep(wait)
        except Exception as error:
            print(f"SKIP page fetch failed: {url} -> {error}")
            return FetchResult(None)
    raise RateLimitError(f"429 after 3 retries on {url}")


def _is_under_root_path(root_url: str, candidate_url: str) -> bool:
    """Check if candidate URL path starts with root URL path."""
    root_path = urlparse(root_url).path.rstrip("/")
    candidate_path = urlparse(candidate_url).path
    if not root_path:
        return True
    return candidate_path.startswith(root_path)


def _discover_bfs(root_url: str) -> set[str]:
    """BFS crawl to discover same-domain product URLs under root path."""
    to_visit = [root_url]
    visited: set[str] = set()
    product_urls: set[str] = set()

    while to_visit and len(visited) < CRAWL_MAX_PAGES_PER_SOURCE:
        current = to_visit.pop(0)
        if current in visited:
            continue
        visited.add(current)

        if current != root_url and not _is_product_url(current):
            continue

        try:
            fetch_result = _fetch_page_html(current)
        except RateLimitError:
            print(f"  bfs: aborted — 429 rate limit after {len(visited)} pages")
            break
        html = fetch_result.html
        if html is None:
            continue

        if current != root_url and _is_product_url(current):
            product_urls.add(current)

        soup = BeautifulSoup(html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            absolute_url = _normalize_http_url(current, href)
            if not absolute_url.startswith(("http://", "https://")):
                continue
            if not _is_same_domain(root_url, absolute_url):
                continue
            if _is_file_link(absolute_url):
                continue
            if not _is_product_url(absolute_url):
                continue
            if not _is_under_root_path(root_url, absolute_url):
                continue
            product_urls.add(absolute_url)
            if absolute_url not in visited:
                to_visit.append(absolute_url)

        time.sleep(WEB_CRAWL_DELAY_SEC)

    print(f"  bfs: visited={len(visited)}, product_urls={len(product_urls)}")
    return product_urls


# URL path prefixes that indicate non-content sections (forums, news, classifieds, etc.)
_SKIP_SITEMAP_PREFIXES = re.compile(
    r"^/(news|novosti|forum|interactive|board|board_el|classified|obyavleniya"
    r"|gallery|galereya|video|press|misc|map|rss|feed|story|top_forum"
    r"|company|companies|kompanii|rassylka|subscribe|quotation|chesnok"
    r"|vacancy|vakansii|wiki|dict|link|exhibition|expo)/",
    re.IGNORECASE,
)


def _is_content_url(url: str) -> bool:
    """Filter for sitemap/search URLs: skip forums, news, classifieds, etc.

    Looser than _is_under_root_path (domain-wide), but skips known junk sections.
    Used for sitemap and search discovery where we want broader coverage.
    """
    path = urlparse(url).path
    if _SKIP_SITEMAP_PREFIXES.search(path):
        return False
    return _is_product_url(url)


def _discover_sitemap(root_url: str) -> set[str]:
    """Discover URLs via sitemap.xml parsing."""
    from sitemap import fetch_sitemap_urls, filter_sitemap_urls

    raw_urls = fetch_sitemap_urls(root_url)
    if not raw_urls:
        print("  sitemap: none found")
        return set()

    # Use looser content filter (not root path restricted) for sitemap
    filtered = filter_sitemap_urls(
        raw_urls,
        root_url,
        is_product_url_fn=_is_content_url,
        is_under_root_path_fn=None,  # Don't restrict to root path for sitemap
    )
    print(f"  sitemap: {len(raw_urls)} raw -> {len(filtered)} filtered")
    return set(filtered)


def _discover_search(root_url: str, search_terms: list[str] | None = None) -> set[str]:
    """Discover URLs via Yandex Cloud Search API."""
    from yandex_search import discover_via_search

    domain = get_domain_name(root_url)
    urls = discover_via_search(
        domain=domain,
        search_terms=search_terms,
        max_queries=SEARCH_MAX_QUERIES_PER_SOURCE,
    )
    # Use looser content filter for search results (not root path restricted)
    filtered = [u for u in urls if _is_content_url(u)]
    print(f"  search: {len(urls)} raw -> {len(filtered)} filtered")
    return set(filtered)


def _discover_web_urls(root_url: str, search_terms: list[str] | None = None) -> List[str]:
    """Multi-strategy URL discovery: sitemap + search API + BFS crawl."""
    all_urls: set[str] = set()

    # Strategy 1: Sitemap (fast, free, no rate limits)
    if SITEMAP_ENABLED:
        print("  Trying sitemap.xml...")
        sitemap_urls = _discover_sitemap(root_url)
        all_urls.update(sitemap_urls)

    # Strategy 2: Yandex Search API (finds pages with broken navigation)
    if SEARCH_DISCOVERY_ENABLED:
        print("  Trying search API discovery...")
        search_urls = _discover_search(root_url, search_terms)
        all_urls.update(search_urls)

    # Strategy 3: BFS crawl (traditional, catches interlinked pages)
    if BFS_ENABLED:
        print("  Running BFS crawl...")
        bfs_urls = _discover_bfs(root_url)
        all_urls.update(bfs_urls)
    else:
        print("  BFS crawl: disabled (BFS_ENABLED=0 or --no-bfs)")

    print(f"  discover total: {len(all_urls)} unique product URLs")
    return _prioritize_urls(all_urls)


# URL path segments that suggest product/spec pages (higher priority)
_PRODUCT_PATH_SIGNALS = re.compile(
    r"/(catalog|katalog|products|product|cable|group-|series|seriya"
    r"|model|item|tovar|produk|oborudovanie|equipment)/",
    re.IGNORECASE,
)

# URL path segments that suggest editorial/info content (lower priority)
_EDITORIAL_PATH_SIGNALS = re.compile(
    r"/(article|articles|story|blog|press|interview|obzor|info"
    r"|question|gosts|services|solutions|view)/",
    re.IGNORECASE,
)


def _prioritize_urls(urls: set[str]) -> List[str]:
    """Sort URLs: product/catalog pages first, then neutral, then editorial."""
    def url_priority(url: str) -> tuple[int, str]:
        path = urlparse(url).path
        if _PRODUCT_PATH_SIGNALS.search(path):
            return (0, url)
        if _EDITORIAL_PATH_SIGNALS.search(path):
            return (2, url)
        return (1, url)

    return sorted(urls, key=url_priority)


def ingest_web(root_url: str, disk_folder: str, resume_urls=None, batch_size=0,
               spa_mode: bool = False) -> Dict[str, Any]:
    """Crawl web pages and ingest product pages.

    Args:
        resume_urls: If provided, skip discovery and use these URLs directly.
        spa_mode: If True, use SPA extraction (inner_text) instead of HTML parsing.
        batch_size: If > 0, process only this many URLs per run (all discovered URLs
                    are still saved to manifest for future resume).
    """
    from hashlib import sha256

    storage = _storage() if UPLOAD_ENABLED else None

    processed = set(load_json(STATE_FILE, []))
    hash_index = load_json(HASH_INDEX_FILE, {})
    dead_urls: set = set(load_json(DEAD_URLS_FILE, []))

    source_domain = sanitize_domain(get_domain_name(root_url))
    ingest_date = date.today().isoformat()

    # Phase 1: discover product URLs via BFS (or load from resume)
    if resume_urls is not None:
        product_pages = resume_urls
        print(f"Resumed {len(product_pages)} URLs from previous manifest (discovery skipped)")
    else:
        print(f"Discovering pages from {root_url}...")
        product_pages = _discover_web_urls(root_url)

    manifest: Dict[str, Any] = {
        "source_page": root_url,
        "source_domain": source_domain,
        "source_type": "web_page",
        "started_at": datetime.utcnow().isoformat(),
        "product_pages_found": len(product_pages),
        "discovered_urls": product_pages,
        "documents": [],
    }

    # Filter out already-processed, dead, and non-product URLs, then apply batch limit
    unprocessed = [u for u in product_pages if u not in processed and u not in dead_urls and _is_product_url(u)]
    skipped_count = len(product_pages) - len(unprocessed)
    if skipped_count:
        print(f"Skipping {skipped_count} already-processed/dead URLs")

    pages_to_process = unprocessed
    if batch_size > 0:
        pages_to_process = unprocessed[:batch_size]
        print(f"Batch mode: processing {len(pages_to_process)} of {len(unprocessed)} remaining URLs")

    # Phase 2: fetch and process product pages
    total_to_process = len(pages_to_process)
    counts = {"ingested": 0, "skipped": 0, "failed": 0, "quarantined": 0}
    _state_dirty = False  # batch state.json writes for performance
    _prefix_404_counts: Dict[str, int] = {}  # track consecutive 404s per URL prefix
    for idx, page_url in enumerate(pages_to_process, 1):
        document_id = _url_to_document_id(root_url, page_url)

        doc_result: Dict[str, Any] = {
            "source_url": page_url,
            "document_id": document_id,
            "status": "started",
            "started_at": datetime.utcnow().isoformat(),
        }
        manifest["documents"].append(doc_result)

        if page_url in processed:
            doc_result["status"] = "skipped_processed"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            counts["skipped"] += 1
            print(f"[{idx}/{total_to_process}] SKIP (processed): {page_url}")
            continue

        if page_url in dead_urls:
            doc_result["status"] = "skipped_dead"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            counts["skipped"] += 1
            continue

        # Prefix-based 404 skip: if N consecutive 404s share a prefix, skip the rest
        url_path = urlparse(page_url).path.rstrip("/")
        url_prefix = url_path.rsplit("/", 1)[0] if "/" in url_path else url_path
        if CONSECUTIVE_404_THRESHOLD > 0 and _prefix_404_counts.get(url_prefix, 0) >= CONSECUTIVE_404_THRESHOLD:
            dead_urls.add(page_url)
            doc_result["status"] = "skipped_dead_prefix"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            counts["skipped"] += 1
            continue

        try:
            result = _fetch_page_html(page_url, spa_mode=spa_mode)
        except RateLimitError as e:
            doc_result["status"] = "rate_limited"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            counts["failed"] += 1
            print(f"\n*** ABORTING: {e}")
            print(f"*** Site is rate-limiting. Processed {idx-1}/{total_to_process} before abort.")
            break
        except CaptchaBlockedError as e:
            doc_result["status"] = "captcha_blocked"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            counts["failed"] += 1
            print(f"\n*** ABORTING: {e}")
            print("*** Run 'python3 browser.py --save-session' to refresh session cookies.")
            print(f"*** Processed {idx-1}/{total_to_process} before abort.")
            break

        if result.is_404:
            dead_urls.add(page_url)
            _prefix_404_counts[url_prefix] = _prefix_404_counts.get(url_prefix, 0) + 1
            n = _prefix_404_counts[url_prefix]
            if n == CONSECUTIVE_404_THRESHOLD:
                print(f"  *** {n} consecutive 404s under {url_prefix}/ — skipping prefix")
            doc_result["status"] = "dead_404"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            counts["failed"] += 1
            continue

        html = result.html
        if html is None:
            doc_result["status"] = "fetch_failed"
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            counts["failed"] += 1
            continue

        # Successful fetch — reset 404 counter for this prefix
        _prefix_404_counts[url_prefix] = 0

        try:
            # Content-hash dedup
            content_hash = sha256(html.encode("utf-8")).hexdigest()
            if content_hash in hash_index:
                doc_result["status"] = "duplicate_content"
                doc_result["sha256"] = content_hash
                doc_result["finished_at"] = datetime.utcnow().isoformat()
                counts["skipped"] += 1
                print(f"[{idx}/{total_to_process}] SKIP (duplicate content): {document_id}")
                processed.add(page_url)
                _state_dirty = True
                continue

            # Extract blocks and check minimum content
            from extractors import extract_web_html_blocks, extract_spa_blocks
            blocks = extract_web_html_blocks(html)
            extraction_mode = "html"
            # SPA fallback: if HTML extraction yields too few blocks, try rendered text
            if len(blocks) < WEB_MIN_CONTENT_BLOCKS and result.rendered_text:
                spa_blocks = extract_spa_blocks(result.rendered_text)
                if len(spa_blocks) > len(blocks):
                    blocks = spa_blocks
                    extraction_mode = "spa"
            if len(blocks) < WEB_MIN_CONTENT_BLOCKS:
                doc_result["status"] = "skipped_sparse"
                doc_result["block_count"] = len(blocks)
                doc_result["finished_at"] = datetime.utcnow().isoformat()
                counts["skipped"] += 1
                print(f"[{idx}/{total_to_process}] SKIP (too sparse, {len(blocks)} blocks): {document_id}")
                processed.add(page_url)
                _state_dirty = True
                continue

            # Check if content is product/spec related
            content_text = "\n".join(blocks)
            spec_score = product_spec_score(content_text, url=page_url)
            if spec_score < WEB_MIN_PRODUCT_SCORE:
                doc_result["status"] = "skipped_not_product"
                doc_result["product_score"] = spec_score
                doc_result["finished_at"] = datetime.utcnow().isoformat()
                counts["skipped"] += 1
                print(f"[{idx}/{total_to_process}] SKIP (not product content, score={spec_score}): {document_id}")
                processed.add(page_url)
                _state_dirty = True
                continue

            output_dir = os.path.join(LOCAL_DATASET_ROOT, DOMAIN, source_domain, document_id)
            os.makedirs(output_dir, exist_ok=True)

            if extraction_mode == "spa":
                from extractors import extract_spa_to_units
                extraction_log = extract_spa_to_units(
                    rendered_text=result.rendered_text,
                    output_dir=output_dir,
                    document_id=document_id,
                    section="web_spa",
                )
            else:
                extraction_log = extract_html_string_to_units(
                    html_text=html,
                    output_dir=output_dir,
                    document_id=document_id,
                    section="web_html",
                )

            units_dir = os.path.join(output_dir, "units")
            chunks_dir = os.path.join(output_dir, "chunks")
            minimal_chunks_dir = os.path.join(output_dir, "chunks_minimal")
            chunking_log = chunk_units_v2(
                units_dir=units_dir,
                chunks_dir=chunks_dir,
                target_tokens=CHUNK_TARGET_TOKENS,
                max_tokens=CHUNK_MAX_TOKENS,
                minimal_chunks_dir=minimal_chunks_dir,
            )
            quality_gate = evaluate_quality_for_document(output_dir, write_report=True)
            quality_status = (quality_gate or {}).get("status", "")
            should_quarantine = QUALITY_GATE_BLOCK_WARN and quality_status == "warn"

            meta = {
                "domain": DOMAIN,
                "document_id": document_id,
                "source_url": page_url,
                "source_type": "web_page",
                "sha256": content_hash,
                "ingested_at": datetime.utcnow().isoformat(),
                "source_domain": source_domain,
            }
            with open(
                os.path.join(output_dir, "meta.json"), "w", encoding="utf-8"
            ) as file:
                json.dump(meta, file, indent=2, ensure_ascii=False)

            hash_index[content_hash] = page_url
            # hash_index saved in batched state save below

            processed_disk_dir = f"{disk_folder}/_processed/{document_id}"
            quarantine_disk_dir = f"{disk_folder}/{QUARANTINE_SUBDIR}/{document_id}"
            target_disk_dir = quarantine_disk_dir if should_quarantine else processed_disk_dir

            uploaded_files = 0
            if storage:
                upload_result = retry(
                    lambda: storage.upload_tree(
                        source=output_dir,
                        destination=target_disk_dir,
                        overwrite=True,
                    )
                )
                uploaded_files = upload_result.files_uploaded

            extraction_info = {
                "mode": "web_html_units_chunks_v2",
                "output_dir": output_dir,
                "extraction_log": extraction_log,
                "chunking_log": chunking_log,
                "quality_gate": quality_gate,
                "quality_status": quality_status,
                "quality_action": "quarantine" if should_quarantine else "pass_to_processed",
                "target_disk_dir": target_disk_dir,
                "processed_files_uploaded": uploaded_files,
            }

            append_metadata(
                {
                    "source_domain": source_domain,
                    "ingest_date": ingest_date,
                    "filename": document_id,
                    "source_url": page_url,
                    "disk_path": target_disk_dir,
                    "sha256": content_hash,
                }
            )

            doc_result["status"] = "quarantined_quality_warn" if should_quarantine else "ingested"
            doc_result["sha256"] = content_hash
            doc_result["extraction"] = extraction_info
            doc_result["finished_at"] = datetime.utcnow().isoformat()

            processed.add(page_url)
            _state_dirty = True
            if should_quarantine:
                counts["quarantined"] += 1
                print(f"[{idx}/{total_to_process}] QUARANTINED (quality warn): {document_id}")
            else:
                counts["ingested"] += 1
                print(f"[{idx}/{total_to_process}] INGESTED: {document_id}")

        except Exception as error:
            doc_result["status"] = "failed"
            doc_result["error"] = str(error)
            doc_result["finished_at"] = datetime.utcnow().isoformat()
            counts["failed"] += 1
            print(f"[{idx}/{total_to_process}] FAILED: {document_id} -> {error}")

        time.sleep(WEB_CRAWL_DELAY_SEC)

        # Batch save state every 10 URLs (avoid 6+10 MB writes on every URL)
        if _state_dirty and idx % 10 == 0:
            save_state_json(STATE_FILE, processed)
            save_dict_json_locked(HASH_INDEX_FILE, hash_index)
            save_dict_json_locked(DEAD_URLS_FILE, sorted(dead_urls))
            _state_dirty = False

        # Progress summary + interim manifest checkpoint every 50 docs
        if idx % 50 == 0:
            elapsed = (datetime.utcnow() - datetime.fromisoformat(manifest["started_at"])).total_seconds()
            rate = idx / elapsed * 3600 if elapsed > 0 else 0
            print(
                f"  ── progress: {idx}/{total_to_process} ({idx*100//total_to_process}%) | "
                f"ingested={counts['ingested']} skip={counts['skipped']} fail={counts['failed']} "
                f"quarantine={counts['quarantined']} | {rate:.0f}/hr ──"
            )

        # Interim manifest checkpoint every 100 docs (enables --resume-from after crash)
        if idx % 100 == 0:
            _interim_counts: Dict[str, int] = {}
            for _d in manifest["documents"]:
                _k = _d.get("status", "unknown")
                _interim_counts[_k] = _interim_counts.get(_k, 0) + 1
            manifest["status_counts"] = _interim_counts
            write_run_manifest(manifest)

    # Final state save
    if _state_dirty:
        save_state_json(STATE_FILE, processed)
        save_dict_json_locked(HASH_INDEX_FILE, hash_index)

    # Persist dead URLs for future runs
    save_dict_json_locked(DEAD_URLS_FILE, sorted(dead_urls))
    dead_new = sum(1 for d in manifest["documents"] if d.get("status") in ("dead_404", "skipped_dead_prefix"))
    if dead_new:
        print(f"  Dead URLs: {dead_new} new, {len(dead_urls)} total cached")

    manifest["finished_at"] = datetime.utcnow().isoformat()

    status_counts: Dict[str, int] = {}
    for item in manifest["documents"]:
        key = item.get("status", "unknown")
        status_counts[key] = status_counts.get(key, 0) + 1
    manifest["status_counts"] = status_counts

    manifest_path = write_run_manifest(manifest)
    print(f"Run manifest: {manifest_path}")

    return manifest


UPLOAD_WORKERS = int(os.environ.get("UPLOAD_WORKERS", "4"))
UPLOADED_TRACKER_FILE = "_uploaded.json"


def _load_uploaded_set(source_dir: str) -> set:
    """Load set of entry names already uploaded from local tracker."""
    path = os.path.join(source_dir, UPLOADED_TRACKER_FILE)
    return set(load_json(path, []))


def _save_uploaded_set(source_dir: str, uploaded: set):
    path = os.path.join(source_dir, UPLOADED_TRACKER_FILE)
    save_json(path, sorted(uploaded))


def _mark_entries_uploaded(source_dir: str, entries: list, uploaded_set: set):
    """Delete local entry dirs and update tracker."""
    for entry in entries:
        entry_path = os.path.join(source_dir, entry)
        if os.path.isdir(entry_path):
            shutil.rmtree(entry_path)
            print(f"  Cleaned up local: {entry}")
        uploaded_set.add(entry)
    _save_uploaded_set(source_dir, uploaded_set)


def batch_upload_to_yandex(source_path: str, disk_base: str = "/datasets/specs") -> Dict[str, Any]:
    """Upload locally stored datasets to Yandex Disk.

    Uses zip-per-source for bulk upload (1 file instead of thousands),
    with parallel workers for multiple sources.

    Args:
        source_path: Relative path under LOCAL_DATASET_ROOT (e.g., "electrical/ekfgroup.com")
        disk_base: Base path on Yandex Disk
    """
    import zipfile
    from concurrent.futures import ThreadPoolExecutor, as_completed

    yd = _yandex()
    local_base = os.path.join(LOCAL_DATASET_ROOT, source_path)
    if not os.path.isdir(local_base):
        raise FileNotFoundError(f"Local directory not found: {local_base}")

    today = date.today().isoformat()
    disk_folder = f"{disk_base}/{source_path}/{today}"

    # Load tracker — skip entries already uploaded
    uploaded_set = _load_uploaded_set(local_base)

    all_entries = [
        e for e in sorted(os.listdir(local_base))
        if os.path.isdir(os.path.join(local_base, e))
        and not e.startswith(".") and not e.startswith("_")
        and e not in uploaded_set
    ]
    total_entries = len(all_entries)

    if uploaded_set:
        print(f"Skipping {len(uploaded_set)} already-uploaded entries")

    if total_entries == 0:
        print("No new documents to upload.")
        return {"uploaded": 0, "failed": 0, "docs_done": 0}

    # For large sources (>100 docs) or single large directories (files mode), zip and upload
    if total_entries > 100:
        return _batch_upload_zipped(local_base, all_entries, disk_folder, yd, uploaded_set)

    # Check if any single entry is very large (e.g., files/ with GBs of PDFs)
    for entry in all_entries:
        entry_path = os.path.join(local_base, entry)
        entry_size = sum(
            os.path.getsize(os.path.join(r, f))
            for r, _, files in os.walk(entry_path) for f in files
        )
        if entry_size > MAX_ZIP_SIZE_MB * 1024 * 1024:
            print(f"Large entry '{entry}' ({entry_size / 1024 / 1024:.0f} MB) — using chunked file upload")
            return _upload_large_dir(entry_path, disk_folder, yd)

    # For smaller sources, upload docs in parallel
    return _batch_upload_parallel(local_base, all_entries, disk_folder, yd, uploaded_set)


MAX_ZIP_SIZE_MB = int(os.environ.get("MAX_ZIP_SIZE_MB", "300"))


def _batch_upload_zipped(
    local_base: str, entries: list, disk_folder: str, yd, uploaded_set: set
) -> Dict[str, Any]:
    """Zip docs into archives and upload. Splits into ~500 MB chunks if needed."""
    import zipfile

    total = len(entries)
    yd.ensure_tree(disk_folder)

    # First pass: measure total size to decide if we need splitting
    total_size = 0
    for entry in entries:
        entry_path = os.path.join(local_base, entry)
        for root, dirs, files in os.walk(entry_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fname in files:
                if not fname.startswith("."):
                    total_size += os.path.getsize(os.path.join(root, fname))

    total_size_mb = total_size / (1024 * 1024)
    need_split = total_size_mb > MAX_ZIP_SIZE_MB * 1.5  # Split if raw size > 750 MB

    if not need_split:
        # Single zip upload (original path)
        return _upload_single_zip(local_base, entries, disk_folder, yd, part_label=None, uploaded_set=uploaded_set)

    # Split into chunks: estimate entries per chunk based on avg size
    avg_entry_size = total_size / max(total, 1)
    entries_per_chunk = max(1, int(MAX_ZIP_SIZE_MB * 1024 * 1024 / max(avg_entry_size, 1)))
    chunks = [entries[i:i + entries_per_chunk] for i in range(0, total, entries_per_chunk)]

    print(f"Large source ({total_size_mb:.0f} MB raw) — splitting into {len(chunks)} parts")

    results = {"uploaded": 0, "failed": 0, "docs_done": 0, "mode": "zip_split"}
    for part_idx, chunk in enumerate(chunks, 1):
        part_result = _upload_single_zip(
            local_base, chunk, disk_folder, yd,
            part_label=f"part{part_idx:02d}",
            uploaded_set=uploaded_set,
        )
        results["uploaded"] += part_result.get("uploaded", 0)
        results["failed"] += part_result.get("failed", 0)
        results["docs_done"] += part_result.get("docs_done", 0)

    return results


def _upload_single_zip(
    local_base: str, entries: list, disk_folder: str, yd,
    part_label: str | None, uploaded_set: set | None = None,
) -> Dict[str, Any]:
    """Zip a set of entries into one archive and upload it."""
    import zipfile

    total = len(entries)
    suffix = f"_{part_label}" if part_label else ""
    zip_name = f"archive{suffix}.zip"
    zip_disk_path = f"{disk_folder}/{zip_name}"

    # Check if archive already exists on disk (crash recovery / re-run)
    if yd.path_exists(zip_disk_path):
        print(f"SKIP (already on disk): {zip_disk_path}")
        if uploaded_set is not None:
            _mark_entries_uploaded(local_base, entries, uploaded_set)
        return {"uploaded": total, "failed": 0, "docs_done": total, "skipped_existing": True}

    zip_path = f"{local_base}{suffix}.zip"

    print(f"Zipping {total} documents{f' ({part_label})' if part_label else ''}...")
    zip_start = datetime.utcnow()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for idx, entry in enumerate(entries, 1):
            entry_path = os.path.join(local_base, entry)
            for root, dirs, files in os.walk(entry_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fname in files:
                    if fname.startswith("."):
                        continue
                    abs_path = os.path.join(root, fname)
                    arc_name = os.path.relpath(abs_path, local_base)
                    zf.write(abs_path, arc_name)
            if idx % 1000 == 0:
                print(f"  zipped {idx}/{total} docs...")

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    elapsed = (datetime.utcnow() - zip_start).total_seconds()
    print(f"Zip complete: {zip_size_mb:.1f} MB in {elapsed:.0f}s")

    print(f"Uploading {zip_size_mb:.1f} MB to {zip_disk_path}...")
    upload_start = datetime.utcnow()
    try:
        retry(lambda: yd.upload_file(zip_path, zip_disk_path, overwrite=True))
        upload_elapsed = (datetime.utcnow() - upload_start).total_seconds()
        print(f"Upload complete in {upload_elapsed:.0f}s ({zip_size_mb/upload_elapsed*8:.1f} Mbps)")
        os.remove(zip_path)
        # Clean up local entries after successful upload
        if uploaded_set is not None:
            _mark_entries_uploaded(local_base, entries, uploaded_set)
        return {"uploaded": total, "failed": 0, "docs_done": total}
    except Exception as e:
        print(f"Upload FAILED: {zip_name} -> {e}")
        os.remove(zip_path)
        return {"uploaded": 0, "failed": total, "docs_done": 0}


def _upload_large_dir(dir_path: str, disk_folder: str, yd) -> Dict[str, Any]:
    """Upload a large flat directory (e.g., files/ with GBs of PDFs) in zip chunks."""
    import zipfile

    # Per-file tracker for this directory
    tracker_path = os.path.join(dir_path, UPLOADED_TRACKER_FILE)
    uploaded_files = set(load_json(tracker_path, []))

    all_files = sorted(
        f for f in os.listdir(dir_path)
        if os.path.isfile(os.path.join(dir_path, f))
        and not f.startswith(".")
        and f != UPLOADED_TRACKER_FILE
        and f not in uploaded_files
    )
    if uploaded_files:
        print(f"Skipping {len(uploaded_files)} already-uploaded files")
    if not all_files:
        print("No new files to upload.")
        return {"uploaded": 0, "failed": 0, "docs_done": 0}

    dir_name = os.path.basename(dir_path)
    max_chunk_bytes = MAX_ZIP_SIZE_MB * 1024 * 1024
    yd.ensure_tree(disk_folder)

    # Split files into chunks by cumulative size
    chunks: list[list[str]] = []
    current_chunk: list[str] = []
    current_size = 0
    for fname in all_files:
        fsize = os.path.getsize(os.path.join(dir_path, fname))
        if current_chunk and current_size + fsize > max_chunk_bytes:
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0
        current_chunk.append(fname)
        current_size += fsize
    if current_chunk:
        chunks.append(current_chunk)

    total_files = len(all_files)
    print(f"Splitting {total_files} files into {len(chunks)} zip chunks (~{MAX_ZIP_SIZE_MB} MB each)")

    results = {"uploaded": 0, "failed": 0, "docs_done": 0, "mode": "chunked_files"}
    for part_idx, chunk_files in enumerate(chunks, 1):
        zip_path = f"{dir_path}_part{part_idx:02d}.zip"
        zip_disk_path = f"{disk_folder}/{dir_name}_part{part_idx:02d}.zip"

        # Check if this chunk archive already exists on disk
        if yd.path_exists(zip_disk_path):
            print(f"SKIP (already on disk): {zip_disk_path}")
            for fname in chunk_files:
                fpath = os.path.join(dir_path, fname)
                if os.path.exists(fpath):
                    os.remove(fpath)
                uploaded_files.add(fname)
            save_json(tracker_path, sorted(uploaded_files))
            results["uploaded"] += len(chunk_files)
            results["docs_done"] += 1
            continue

        print(f"Zipping part {part_idx}/{len(chunks)} ({len(chunk_files)} files)...")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for fname in chunk_files:
                zf.write(os.path.join(dir_path, fname), f"{dir_name}/{fname}")

        zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)

        print(f"Uploading {zip_size_mb:.1f} MB to {zip_disk_path}...")
        upload_start = datetime.utcnow()
        try:
            retry(lambda: yd.upload_file(zip_path, zip_disk_path, overwrite=True))
            elapsed = (datetime.utcnow() - upload_start).total_seconds()
            print(f"Part {part_idx} uploaded in {elapsed:.0f}s ({zip_size_mb/elapsed*8:.1f} Mbps)")
            results["uploaded"] += len(chunk_files)
            results["docs_done"] += 1
            # Delete uploaded source files
            for fname in chunk_files:
                fpath = os.path.join(dir_path, fname)
                if os.path.exists(fpath):
                    os.remove(fpath)
                uploaded_files.add(fname)
            save_json(tracker_path, sorted(uploaded_files))
        except Exception as e:
            print(f"Part {part_idx} FAILED: {e}")
            results["failed"] += len(chunk_files)
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    print(f"Chunked upload done: {results['uploaded']}/{total_files} files in {len(chunks)} parts")
    return results


def _batch_upload_parallel(
    local_base: str, entries: list, disk_folder: str, yd, uploaded_set: set
) -> Dict[str, Any]:
    """Upload individual doc directories in parallel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    # Pre-create the base tree once
    yd.ensure_tree(f"{disk_folder}/_processed")
    yd.ensure_tree(f"{disk_folder}/{QUARANTINE_SUBDIR}")

    # Check disk for entries that already exist (crash recovery / re-run dedup)
    existing_on_disk: set = set()
    for sub in ("_processed", QUARANTINE_SUBDIR):
        try:
            for item in yd.list_all(f"{disk_folder}/{sub}"):
                existing_on_disk.add(item.get("name", ""))
        except Exception:
            pass  # Folder may not exist yet

    if existing_on_disk:
        skipped = [e for e in entries if e in existing_on_disk]
        if skipped:
            print(f"Skipping {len(skipped)} entries already on disk")
            _mark_entries_uploaded(local_base, skipped, uploaded_set)
            entries = [e for e in entries if e not in existing_on_disk]

    total = len(entries)
    if total == 0:
        print("No new entries to upload.")
        return {"uploaded": 0, "failed": 0, "docs_done": 0}

    results = {"uploaded": 0, "failed": 0, "docs_done": 0, "errors": []}
    results_lock = threading.Lock()
    upload_start = datetime.utcnow()
    counter = {"done": 0}

    def upload_one(entry: str) -> tuple[str, bool, int, str]:
        entry_path = os.path.join(local_base, entry)
        target_dir = f"{disk_folder}/_processed/{entry}"

        qr = os.path.join(entry_path, "quality_report.json")
        if os.path.exists(qr):
            try:
                report = load_json(qr, {})
                if report.get("status") == "warn":
                    target_dir = f"{disk_folder}/{QUARANTINE_SUBDIR}/{entry}"
            except Exception:
                pass

        try:
            yd.ensure_tree(target_dir)
            count = retry(lambda: yd.upload_directory(
                local_dir=entry_path, disk_dir=target_dir, overwrite=True,
            ))
            return entry, True, count, ""
        except Exception as e:
            return entry, False, 0, str(e)

    workers = min(UPLOAD_WORKERS, total)
    print(f"Uploading {total} docs with {workers} workers...")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(upload_one, e): e for e in entries}
        for future in as_completed(futures):
            entry, ok, count, err = future.result()
            counter["done"] += 1
            idx = counter["done"]

            if ok:
                with results_lock:
                    results["uploaded"] += count
                    results["docs_done"] += 1
                # Clean up local entry (main thread, no lock needed for filesystem)
                entry_path = os.path.join(local_base, entry)
                if os.path.isdir(entry_path):
                    shutil.rmtree(entry_path)
                uploaded_set.add(entry)
                print(f"[{idx}/{total}] UPLOADED: {entry} ({count} files)")
            else:
                with results_lock:
                    results["failed"] += 1
                    results["errors"].append({"document": entry, "error": err})
                print(f"[{idx}/{total}] UPLOAD FAILED: {entry} -> {err}")

            # Periodic tracker flush + progress
            if idx % 10 == 0:
                _save_uploaded_set(local_base, uploaded_set)
            if idx % 50 == 0:
                elapsed = (datetime.utcnow() - upload_start).total_seconds()
                rate = idx / elapsed * 3600 if elapsed > 0 else 0
                print(
                    f"  ── upload progress: {idx}/{total} ({idx*100//total}%) | "
                    f"{results['uploaded']} files, {results['failed']} failed | {rate:.0f} docs/hr ──"
                )

    # Final tracker save
    _save_uploaded_set(local_base, uploaded_set)
    print(f"Batch upload done: {results['docs_done']} docs ({results['uploaded']} files), {results['failed']} failed")
    return results


def load_approved_sources_v2(path: str = APPROVED_SOURCES_FILE) -> List[Dict[str, Any]]:
    """Load approved sources with mode field. Returns list of dicts with url and mode."""
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as error:
        print(f"WARNING: failed to read {path}: {error}")
        return []

    sources = payload.get("sources", [])
    approved_items = [item for item in sources if item.get("approved") is True]
    approved_items.sort(key=lambda item: int(item.get("priority", 999999)))

    result = []
    for item in approved_items:
        url = str(item.get("url", "")).strip()
        if url and url.startswith(("http://", "https://")):
            result.append({
                "url": url,
                "mode": item.get("mode", "files"),
            })

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Spec scraper: file and web page modes")
    parser.add_argument("--web", metavar="URL", help="Scrape web pages from URL")
    parser.add_argument("--files", metavar="URL", help="Scrape file links from URL")
    parser.add_argument("--resume-from", metavar="MANIFEST", help="Path to previous run manifest JSON (skip discovery)")
    parser.add_argument("--batch-size", type=int, default=0, metavar="N", help="Process only N URLs per run (0 = all)")
    parser.add_argument("--upload-local", metavar="PATH", help="Upload local datasets to Yandex Disk (e.g., electrical/ekfgroup.com)")
    parser.add_argument("--no-upload", action="store_true", help="Skip Yandex Disk uploads (crawl locally only)")
    parser.add_argument("--spa", action="store_true", help="SPA mode: use rendered inner text for extraction (for JS-heavy sites)")
    parser.add_argument("--no-bfs", action="store_true", help="Skip BFS discovery (use sitemap + search only, avoids rate limits)")
    parser.add_argument("--min-score", type=int, default=None, metavar="N", help="Override WEB_MIN_PRODUCT_SCORE (e.g., 0 for normative doc sources)")
    args = parser.parse_args()

    if args.no_upload:
        UPLOAD_ENABLED = False
    if args.no_bfs:
        BFS_ENABLED = False
    if args.min_score is not None:
        WEB_MIN_PRODUCT_SCORE = args.min_score

    today = date.today().isoformat()

    if args.upload_local:
        print(f"\n=== Uploading local datasets: {args.upload_local} ===")
        batch_upload_to_yandex(args.upload_local)

    elif args.web:
        source_name = sanitize_domain(get_domain_name(args.web))
        disk_folder = f"/datasets/specs/{source_name}/{today}"
        print(f"\n=== Web scraping: {args.web} ===")

        resume_urls = None
        if args.resume_from:
            print(f"Loading URLs from previous manifest: {args.resume_from}")
            prev_manifest = load_json(args.resume_from, {})
            all_urls = prev_manifest.get("discovered_urls", [])
            # Filter out URLs that failed in the previous run
            failed_urls = set()
            for doc in prev_manifest.get("documents", []):
                if doc.get("status") in ("fetch_failed", "failed"):
                    failed_urls.add(doc.get("source_url"))
            resume_urls = [u for u in all_urls if u not in failed_urls]
            print(f"  Total URLs: {len(all_urls)}, after filtering failed: {len(resume_urls)}")

        ingest_web(args.web, disk_folder, resume_urls=resume_urls, batch_size=args.batch_size,
                   spa_mode=args.spa)

    elif args.files:
        source_name = sanitize_domain(get_domain_name(args.files))
        disk_folder = f"/datasets/specs/{source_name}/{today}"
        print(f"\n=== File scraping: {args.files} ===")
        ingest_page(args.files, disk_folder)

    else:
        # Default: process approved sources (backward compatible)
        sources_v2 = load_approved_sources_v2(APPROVED_SOURCES_FILE)

        if not sources_v2:
            FALLBACK_SOURCES = [
                "https://www.elektromir.org/kompaniya/pdf-katalogi",
            ]
            sources_v2 = [{"url": url, "mode": "files"} for url in FALLBACK_SOURCES]
            print("Using fallback SOURCES list (no approved sources found).")
        else:
            print(f"Using approved sources from {APPROVED_SOURCES_FILE}: {len(sources_v2)}")

        for source in sources_v2:
            source_url = source["url"]
            mode = source["mode"]
            source_name = sanitize_domain(get_domain_name(source_url))
            disk_folder = f"/datasets/specs/{source_name}/{today}"

            print(f"\n=== Processing source ({mode}): {source_url} ===")
            if mode == "web":
                ingest_web(source_url, disk_folder)
            else:
                ingest_page(source_url, disk_folder)
