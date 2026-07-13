import os
import threading
from typing import Dict, List, Optional, Set

import requests

YANDEX_API_UPLOAD = "https://cloud-api.yandex.net/v1/disk/resources/upload"
YANDEX_API_RESOURCES = "https://cloud-api.yandex.net/v1/disk/resources"

TOKEN = os.environ.get("YANDEX_DISK_TOKEN")
if not TOKEN:
    raise RuntimeError("YANDEX_DISK_TOKEN is not set. Export it before running the script.")

HEADERS = {"Authorization": f"OAuth {TOKEN}"}
YANDEX_API_DOWNLOAD = "https://cloud-api.yandex.net/v1/disk/resources/download"

# Folder cache — avoid redundant ensure_folder API calls
_folder_cache: Set[str] = set()
_folder_cache_lock = threading.Lock()


def ensure_folder(path: str) -> None:
    with _folder_cache_lock:
        if path in _folder_cache:
            return

    response = requests.put(
        YANDEX_API_RESOURCES,
        headers=HEADERS,
        params={"path": path},
        timeout=30,
    )
    if response.status_code not in (201, 409):
        raise Exception(f"Folder create failed: {response.status_code} {response.text}")

    with _folder_cache_lock:
        _folder_cache.add(path)


def ensure_tree(path: str) -> None:
    """Create nested folder path segment by segment (with cache)."""
    norm = path.strip()
    if not norm or norm == "/":
        return

    # Check if full path already cached
    with _folder_cache_lock:
        if norm in _folder_cache:
            return

    parts = [part for part in norm.split("/") if part]
    current = ""
    for part in parts:
        current = f"{current}/{part}"
        ensure_folder(current)

    with _folder_cache_lock:
        _folder_cache.add(norm)


def path_exists(path: str) -> bool:
    response = requests.get(
        YANDEX_API_RESOURCES,
        headers=HEADERS,
        params={"path": path},
        timeout=30,
    )
    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    raise Exception(f"Path check failed: {response.status_code} {response.text}")


def delete_path(path: str) -> None:
    response = requests.delete(
        YANDEX_API_RESOURCES,
        headers=HEADERS,
        params={"path": path, "permanently": True},
        timeout=30,
    )
    if response.status_code not in (200, 202, 204):
        raise Exception(f"Delete failed: {response.status_code} {response.text}")


def get_file_hash(path: str) -> Optional[str]:
    response = requests.get(
        YANDEX_API_RESOURCES,
        headers=HEADERS,
        params={"path": path, "fields": "sha256"},
        timeout=30,
    )
    if response.status_code == 200:
        return response.json().get("sha256")
    if response.status_code == 404:
        return None
    raise Exception(f"Hash fetch failed: {response.status_code} {response.text}")


def list_directory(path: str, limit: int = 200, offset: int = 0) -> List[Dict]:
    """List one page of resources in a Yandex Disk folder."""
    response = requests.get(
        YANDEX_API_RESOURCES,
        headers=HEADERS,
        params={
            "path": path,
            "limit": limit,
            "offset": offset,
            "fields": "_embedded.items.path,_embedded.items.type,_embedded.items.name",
        },
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json()
    embedded = payload.get("_embedded", {})
    return embedded.get("items", [])


def list_all(path: str) -> List[Dict]:
    """List all items in a Yandex Disk folder, paginating automatically."""
    items: List[Dict] = []
    offset = 0
    page_size = 200
    while True:
        page = list_directory(path, limit=page_size, offset=offset)
        if not page:
            break
        items.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return items


def get_download_url(path: str) -> str:
    response = requests.get(
        YANDEX_API_DOWNLOAD,
        headers=HEADERS,
        params={"path": path},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["href"]


def download_file(path: str, local_path: str) -> None:
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    download_url = get_download_url(path)

    with requests.get(download_url, stream=True, timeout=1800) as response:
        response.raise_for_status()
        with open(local_path, "wb") as out:
            for chunk in response.iter_content(chunk_size=16 * 1024 * 1024):
                if chunk:
                    out.write(chunk)


def _get_upload_url(disk_path: str, overwrite: bool = False) -> str:
    response = requests.get(
        YANDEX_API_UPLOAD,
        headers=HEADERS,
        params={"path": disk_path, "overwrite": overwrite},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["href"]


def upload_by_url(file_url: str, disk_path: str) -> None:
    response = requests.post(
        YANDEX_API_UPLOAD,
        headers=HEADERS,
        params={"url": file_url, "path": disk_path, "overwrite": False},
        timeout=60,
    )
    if response.status_code not in (200, 201, 202):
        raise Exception(f"Upload failed: {response.status_code} {response.text}")


def upload_bytes(data: bytes, disk_path: str, overwrite: bool = False) -> None:
    upload_url = _get_upload_url(disk_path, overwrite=overwrite)
    response = requests.put(upload_url, data=data, timeout=300)
    response.raise_for_status()


def upload_file(local_path: str, disk_path: str, overwrite: bool = False) -> None:
    """Upload file with stream-like behavior (no full in-memory read)."""
    upload_url = _get_upload_url(disk_path, overwrite=overwrite)

    with open(local_path, "rb") as file_obj:
        response = requests.put(upload_url, data=file_obj, timeout=1800)
    response.raise_for_status()


def upload_directory(
    local_dir: str,
    disk_dir: str,
    overwrite: bool = True,
    skip_hidden: bool = True,
) -> int:
    """Upload all files from local_dir to disk_dir recursively."""
    if not os.path.isdir(local_dir):
        raise FileNotFoundError(f"Local directory not found: {local_dir}")

    ensure_tree(disk_dir)
    uploaded = 0

    for root, dirs, files in os.walk(local_dir):
        rel_dir = os.path.relpath(root, local_dir)
        if rel_dir == ".":
            rel_dir = ""

        if skip_hidden:
            dirs[:] = [name for name in dirs if not name.startswith(".")]
            files = [name for name in files if not name.startswith(".")]

        current_disk_dir = disk_dir
        if rel_dir:
            current_disk_dir = f"{disk_dir}/{rel_dir.replace(os.sep, '/')}"
            ensure_tree(current_disk_dir)

        for name in files:
            local_path = os.path.join(root, name)
            disk_path = f"{current_disk_dir}/{name}"
            upload_file(local_path, disk_path, overwrite=overwrite)
            uploaded += 1

    return uploaded
