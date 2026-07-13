"""Sitemap.xml parser for URL discovery."""
import gzip
import io
import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import urlparse

import requests

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# XML namespaces used in sitemaps
_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _fetch_xml(url: str, timeout: int = 30) -> str | None:
    """Fetch URL and return XML text. Handles gzipped content."""
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return None
        if url.endswith(".gz") or resp.headers.get("Content-Type", "").startswith("application/gzip"):
            return gzip.decompress(resp.content).decode("utf-8")
        return resp.text
    except Exception:
        return None


def _parse_sitemap_urls(xml_text: str) -> tuple[list[str], list[str]]:
    """Parse sitemap XML, return (page_urls, sub_sitemap_urls)."""
    page_urls: list[str] = []
    sub_sitemaps: list[str] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return page_urls, sub_sitemaps

    tag = root.tag.lower()

    # Sitemap index — contains links to other sitemaps
    if "sitemapindex" in tag:
        for sitemap_el in root.findall("sm:sitemap/sm:loc", _NS):
            if sitemap_el.text:
                sub_sitemaps.append(sitemap_el.text.strip())
        # Also try without namespace (some sites don't use it)
        if not sub_sitemaps:
            for sitemap_el in root.iter():
                if sitemap_el.tag.endswith("}loc") or sitemap_el.tag == "loc":
                    parent_tag = ""
                    # Walk up — hacky but ET doesn't have parent refs
                    for parent in root.iter():
                        for child in parent:
                            if child is sitemap_el:
                                parent_tag = parent.tag
                                break
                    if "sitemap" in parent_tag.lower() and sitemap_el.text:
                        sub_sitemaps.append(sitemap_el.text.strip())

    # URL set — contains actual page URLs
    elif "urlset" in tag:
        for url_el in root.findall("sm:url/sm:loc", _NS):
            if url_el.text:
                page_urls.append(url_el.text.strip())
        # Try without namespace
        if not page_urls:
            for el in root.iter():
                if (el.tag.endswith("}loc") or el.tag == "loc") and el.text:
                    page_urls.append(el.text.strip())

    return page_urls, sub_sitemaps


def _check_robots_for_sitemaps(base_url: str) -> list[str]:
    """Check robots.txt for Sitemap directives."""
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = requests.get(robots_url, headers=REQUEST_HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        sitemaps = []
        for line in resp.text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("sitemap:"):
                url = stripped.split(":", 1)[1].strip()
                if url.startswith("http"):
                    sitemaps.append(url)
        return sitemaps
    except Exception:
        return []


def fetch_sitemap_urls(base_url: str, max_sitemaps: int = 20) -> list[str]:
    """Discover URLs from sitemap.xml, sitemap index, and robots.txt.

    Returns deduplicated list of all URLs found.
    """
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    # Collect candidate sitemap URLs to try
    sitemap_candidates = [
        f"{origin}/sitemap.xml",
        f"{origin}/sitemap_index.xml",
        f"{origin}/sitemap.xml.gz",
    ]

    # Check robots.txt for additional sitemap locations
    robots_sitemaps = _check_robots_for_sitemaps(base_url)
    sitemap_candidates.extend(robots_sitemaps)

    # Deduplicate candidates
    seen_sitemaps: set[str] = set()
    to_process: list[str] = []
    for url in sitemap_candidates:
        if url not in seen_sitemaps:
            seen_sitemaps.add(url)
            to_process.append(url)

    all_urls: set[str] = set()
    processed_count = 0

    while to_process and processed_count < max_sitemaps:
        sitemap_url = to_process.pop(0)
        processed_count += 1

        xml_text = _fetch_xml(sitemap_url)
        if xml_text is None:
            continue

        page_urls, sub_sitemaps = _parse_sitemap_urls(xml_text)
        all_urls.update(page_urls)

        for sub in sub_sitemaps:
            if sub not in seen_sitemaps:
                seen_sitemaps.add(sub)
                to_process.append(sub)

    return sorted(all_urls)


def filter_sitemap_urls(
    urls: list[str],
    root_url: str,
    is_product_url_fn=None,
    is_under_root_path_fn=None,
) -> list[str]:
    """Filter sitemap URLs to same domain, under root path, product pages only.

    Args:
        urls: Raw URLs from sitemap
        root_url: The root URL used for path filtering
        is_product_url_fn: Optional callable(url) -> bool (from scraper._is_product_url)
        is_under_root_path_fn: Optional callable(root, url) -> bool
    """
    root_domain = urlparse(root_url).netloc.replace("www.", "")
    filtered = []

    for url in urls:
        parsed = urlparse(url)
        # Same domain check
        domain = parsed.netloc.replace("www.", "")
        if domain != root_domain:
            continue
        # Skip file links
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in (".pdf", ".doc", ".docx", ".xls", ".xlsx")):
            continue
        # Skip image/media links
        if any(path_lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".mp4", ".mp3")):
            continue
        # Product URL filter
        if is_product_url_fn and not is_product_url_fn(url):
            continue
        # Path filter (if provided)
        if is_under_root_path_fn and not is_under_root_path_fn(root_url, url):
            continue
        filtered.append(url)

    return filtered
