"""Yandex Cloud Search API v2 integration for URL discovery.

Uses the synchronous web search endpoint.
Pricing: ~$4/1000 sync queries, ~$0.25/1000 deferred queries.
Docs: https://yandex.cloud/en/docs/search-api/

Requires env vars:
  YANDEX_SEARCH_API_KEY — Yandex Cloud API key (service account with search-api.webSearch.user role)
  YANDEX_SEARCH_FOLDER_ID — Yandex Cloud folder ID
"""
import base64
import os
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import requests

# Synchronous search endpoint
YANDEX_SEARCH_ENDPOINT = "https://searchapi.api.cloud.yandex.net/v2/web/search"
# Async (deferred) endpoint — cheaper but requires polling
YANDEX_SEARCH_ASYNC_ENDPOINT = "https://searchapi.api.cloud.yandex.net/v2/web/searchAsync"
YANDEX_OPERATIONS_ENDPOINT = "https://operation.api.cloud.yandex.net/operations"

# Default search terms for electrical equipment sources
DEFAULT_SEARCH_TERMS = [
    "кабель характеристики",
    "провод технические данные",
    "автомат модульный",
    "контактор",
    "реле",
    "щит распределительный",
    "ГОСТ кабель",
    "сечение жил",
    "каталог продукции",
    "технические характеристики",
]


def _get_credentials() -> tuple[str, str] | None:
    """Return (api_key, folder_id) or None if not configured."""
    api_key = os.environ.get("YANDEX_SEARCH_API_KEY", "").strip()
    folder_id = os.environ.get("YANDEX_SEARCH_FOLDER_ID", "").strip()
    if api_key and folder_id:
        return api_key, folder_id
    return None


def _parse_search_xml(xml_text: str) -> list[str]:
    """Extract URLs from Yandex search XML response."""
    urls = []
    try:
        root = ET.fromstring(xml_text)
        # Structure: <yandexsearch><response><results><grouping><group><doc><url>
        for doc in root.iter("doc"):
            url_el = doc.find("url")
            if url_el is not None and url_el.text:
                urls.append(url_el.text.strip())
    except ET.ParseError:
        pass
    return urls


def yandex_search_sync(
    query: str, api_key: str, folder_id: str, page: int = 0, lr: int = 213
) -> list[str]:
    """Synchronous Yandex Cloud search. Returns list of result URLs.

    ~$4 per 1000 queries. Results returned immediately.
    """
    headers = {"Authorization": f"Api-Key {api_key}"}
    body = {
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query,
            "page": str(page),
        },
        "groupSpec": {
            "groupMode": "GROUP_MODE_DEEP",
            "groupsOnPage": "50",
            "docsInGroup": "1",
        },
        "folderId": folder_id,
        "responseFormat": "FORMAT_XML",
        "region": str(lr),
    }

    try:
        resp = requests.post(YANDEX_SEARCH_ENDPOINT, json=body, headers=headers, timeout=30)
    except Exception as e:
        print(f"  search error: {e}")
        return []

    if resp.status_code == 403:
        print("  search: auth failed or quota exceeded (403)")
        return []
    if resp.status_code == 429:
        print("  search: rate limited (429)")
        return []
    if resp.status_code != 200:
        print(f"  search: HTTP {resp.status_code}")
        return []

    # Response has rawData field with base64-encoded XML
    try:
        data = resp.json()
        raw_data = data.get("rawData", "")
        if raw_data:
            xml_text = base64.b64decode(raw_data).decode("utf-8")
            return _parse_search_xml(xml_text)
    except Exception as e:
        print(f"  search: response parse error: {e}")

    return []


def yandex_search_deferred(
    query: str, api_key: str, folder_id: str, page: int = 0, lr: int = 213,
    poll_interval: float = 5.0, max_wait: float = 300.0,
) -> list[str]:
    """Deferred (async) Yandex Cloud search. Cheaper (~$0.25/1000) but slower.

    Submits query, polls for result. Typically takes seconds to minutes.
    """
    headers = {"Authorization": f"Api-Key {api_key}"}
    body = {
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query,
            "page": str(page),
        },
        "groupSpec": {
            "groupMode": "GROUP_MODE_DEEP",
            "groupsOnPage": "50",
            "docsInGroup": "1",
        },
        "folderId": folder_id,
        "responseFormat": "FORMAT_XML",
        "region": str(lr),
    }

    # Submit async request
    try:
        resp = requests.post(YANDEX_SEARCH_ASYNC_ENDPOINT, json=body, headers=headers, timeout=30)
    except Exception as e:
        print(f"  search error: {e}")
        return []

    if resp.status_code not in (200, 201):
        print(f"  search async submit: HTTP {resp.status_code}")
        return []

    try:
        op = resp.json()
        op_id = op.get("id")
        if not op_id:
            print("  search: no operation ID in response")
            return []
    except Exception as e:
        print(f"  search: response parse error: {e}")
        return []

    # Poll for result
    waited = 0.0
    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval

        try:
            poll_resp = requests.get(
                f"{YANDEX_OPERATIONS_ENDPOINT}/{op_id}",
                headers=headers,
                timeout=30,
            )
            if poll_resp.status_code != 200:
                continue

            result = poll_resp.json()
            if result.get("done"):
                raw_data = result.get("response", {}).get("rawData", "")
                if raw_data:
                    xml_text = base64.b64decode(raw_data).decode("utf-8")
                    return _parse_search_xml(xml_text)
                return []
        except Exception:
            continue

    print(f"  search: operation {op_id} timed out after {max_wait}s")
    return []


def discover_via_search(
    domain: str,
    search_terms: list[str] | None = None,
    max_queries: int = 50,
    pages_per_term: int = 3,
    delay_sec: float = 1.0,
    use_deferred: bool = True,
) -> list[str]:
    """Discover URLs for a domain via Yandex Cloud Search API.

    Args:
        domain: Target domain (e.g., "ruscable.ru")
        search_terms: Search terms to combine with site: operator.
        max_queries: Maximum total API queries to use (budget).
        pages_per_term: How many result pages to fetch per term.
        delay_sec: Delay between API calls (sync mode).
        use_deferred: Use cheaper deferred mode ($0.25/1000 vs $4/1000).
    """
    creds = _get_credentials()
    if creds is None:
        print("  search discovery: YANDEX_SEARCH_API_KEY/FOLDER_ID not set, skipping")
        return []

    api_key, folder_id = creds
    terms = search_terms or DEFAULT_SEARCH_TERMS
    search_fn = yandex_search_deferred if use_deferred else yandex_search_sync

    all_urls: set[str] = set()
    queries_used = 0
    target_domain = domain.replace("www.", "")

    for term in terms:
        if queries_used >= max_queries:
            break

        query = f"site:{domain} {term}"

        for page in range(pages_per_term):
            if queries_used >= max_queries:
                break

            urls = search_fn(query, api_key, folder_id, page=page)
            queries_used += 1

            if not urls:
                break  # No more results for this term

            for url in urls:
                url_domain = urlparse(url).netloc.replace("www.", "")
                if url_domain == target_domain:
                    all_urls.add(url)

            if not use_deferred:
                time.sleep(delay_sec)

    print(f"  search discovery: {queries_used} queries, {len(all_urls)} unique URLs found")
    return sorted(all_urls)
