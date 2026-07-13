#!/usr/bin/env python3
"""Discover candidate websites to scrape for technical documentation.

Searches via Yandex/Google, scores candidates by relevance to the
configured industry profile, optionally probes pages for content type
(web catalogue vs file downloads), and deduplicates by domain.

Profiles are stored in config/profiles/{name}.json — add new profiles
without changing code.

Usage:
    python scripts/discover_sources.py --profile electrical --probe
    python scripts/discover_sources.py --profile electrical --engine both --top-n 30
    python scripts/discover_sources.py --profile electrical --research path/to/seeds.md
"""
import argparse
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
PROFILES_DIR = os.path.join(PROJECT_ROOT, "config", "profiles")
DISCOVERY_DIR = os.path.join(PROJECT_ROOT, "discovery")

BASE_RELEVANCE_TERMS = (
    "каталог", "специф", "паспорт", "техническ", "норм",
    "gost", "snip", "bim",
)

NEGATIVE_TERMS = (
    "google play", "internet explorer", "game", "youtube", "casino", "bet",
)

DENY_DOMAINS = {
    "youtube.com", "facebook.com", "instagram.com", "vk.com", "t.me",
    "play.google.com", "support.google.com", "google.com", "bing.com",
}

FILE_EXT_PATTERN = re.compile(r"\.(pdf|docx?|xlsx?|xml|html?)($|\?)", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s)\]>\"']+", re.IGNORECASE)
DOMAIN_PATTERN = re.compile(
    r"\b([a-z0-9][a-z0-9-]{1,62}\.(?:ru|com|net|org|info|gov\.ru|mos\.ru))\b",
    re.IGNORECASE,
)

# Patterns that indicate non-product pages (simplified from scraper.py _SKIP_URL_SEGMENTS)
_NON_PRODUCT_PATTERN = re.compile(
    r"(checkout|cart|login|auth|payment|delivery|dostavka|oplata|"
    r"contacts|about|vacancy|career|blog|faq|help|support|"
    r"return|warranty|reviews|wishlist|leasing|insurance|"
    r"news|press|forum|wiki|sitemap)",
    re.IGNORECASE,
)

_PAGINATION_PATTERN = re.compile(
    r"[?&](page|p|pg|start|offset)=\d+", re.IGNORECASE,
)


def _load_profile(name: str) -> Dict:
    """Load and validate ``config/profiles/{name}.json``."""
    from doc_harvester.profiles import load_profile

    return load_profile(name, profiles_dir=PROFILES_DIR).to_dict()


def _list_profiles() -> List[str]:
    """List available validated profile filenames."""
    from doc_harvester.profiles import list_profiles

    return list_profiles(PROFILES_DIR)


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return clean.rstrip("/")


def _decode_redirect_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("/url?"):
        query = parse_qs(urlparse(href).query)
        return unquote(query.get("q", [""])[0])

    parsed = urlparse(href)
    query = parse_qs(parsed.query)
    for key in ("url", "q", "target"):
        if key in query and query[key]:
            candidate = unquote(query[key][0])
            if candidate.startswith(("http://", "https://")):
                return candidate

    if href.startswith(("http://", "https://")):
        return href
    return ""


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def _search_with_retry(search_fn, query: str, limit: int, retries: int = 1) -> List[str]:
    """Call search_fn with retry on failure."""
    for attempt in range(retries + 1):
        try:
            results = search_fn(query, limit)
            if results:
                return results
        except Exception as e:
            if attempt < retries:
                print(f"  Search failed ({e}), retrying in 5s...")
                time.sleep(5)
            else:
                print(f"  Search failed ({e}), skipping")
    return []


def search_yandex(query: str, limit: int = 20) -> List[str]:
    url = f"https://yandex.ru/search/?text={quote_plus(query)}"
    response = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results: List[str] = []
    selectors = [
        "a.Link.Link_theme_normal.OrganicTitle-Link",
        "a.OrganicTitle-Link",
        "li.serp-item a[href]",
    ]
    for selector in selectors:
        for a_tag in soup.select(selector):
            href = _decode_redirect_url(a_tag.get("href", ""))
            href = _normalize_url(href)
            if href:
                results.append(href)
            if len(results) >= limit:
                return results
    return results


def search_google(query: str, limit: int = 20) -> List[str]:
    url = f"https://www.google.com/search?q={quote_plus(query)}&num={max(limit, 10)}"
    response = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results: List[str] = []
    for a_tag in soup.select("div.yuRUbf a[href], a[href^='/url?']"):
        href = _decode_redirect_url(a_tag.get("href", ""))
        href = _normalize_url(href)
        if href:
            results.append(href)
        if len(results) >= limit:
            break
    return results


def extract_research_sources(path: str) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8") as file:
            text = file.read()
    except Exception:
        return []

    urls: Set[str] = set()
    for raw in URL_PATTERN.findall(text):
        norm = _normalize_url(raw.rstrip(".,;"))
        if norm:
            urls.add(norm)
    for match in DOMAIN_PATTERN.findall(text):
        domain = match.lower().strip(".")
        if domain not in DENY_DOMAINS:
            urls.add(f"https://{domain}")
    return sorted(urls)


def score_candidate(url: str, profile: Dict) -> int:
    score = 0
    lower = url.lower()

    if FILE_EXT_PATTERN.search(lower):
        score += 30
    if any(term in lower for term in BASE_RELEVANCE_TERMS):
        score += 10
    for term in profile["priority_terms"]:
        if term in lower:
            score += 8
    for dom_hint in profile["priority_domains"]:
        if dom_hint in _domain(lower):
            score += 12
    if any(term in lower for term in NEGATIVE_TERMS):
        score -= 30
    return score


def probe_source(url: str, profile: Dict) -> Dict:
    """Probe a URL to detect content type (web catalogue vs file downloads)."""
    info = {
        "url": url,
        "file_links_found": 0,
        "product_links_found": 0,
        "has_pagination": False,
        "relevance_hits": 0,
        "mode": "unknown",
        "status": "ok",
    }

    priority_terms = profile["priority_terms"]

    try:
        response = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            info["file_links_found"] = 1 if FILE_EXT_PATTERN.search(url) else 0
            info["mode"] = "files" if info["file_links_found"] else "unknown"
            return info

        soup = BeautifulSoup(response.text, "html.parser")
        file_count = 0
        product_count = 0
        relevance_hits = 0
        page_domain = _domain(url)

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = (a_tag.get_text(" ", strip=True) or "").lower()
            href_low = href.lower()

            # Count file download links
            if FILE_EXT_PATTERN.search(href_low):
                file_count += 1

            # Count internal product-style links
            href_parsed = urlparse(href)
            link_domain = href_parsed.netloc.lower().replace("www.", "") if href_parsed.netloc else page_domain
            if (link_domain == page_domain or not href_parsed.netloc) and not _NON_PRODUCT_PATTERN.search(href_low):
                path = href_parsed.path.lower()
                # Links with meaningful paths (not just /, #, javascript:)
                if path and path != "/" and not href.startswith(("#", "javascript:", "mailto:")):
                    if any(ext in path for ext in (".php", ".html", ".htm")) or "/" in path.strip("/"):
                        product_count += 1

            # Count relevance hits
            if any(term in text or term in href_low for term in priority_terms):
                relevance_hits += 1

        # Detect pagination
        has_pagination = bool(_PAGINATION_PATTERN.search(response.text))
        if not has_pagination:
            # Check for numbered navigation links
            nav_numbers = soup.find_all("a", string=re.compile(r"^\d+$"))
            has_pagination = len(nav_numbers) >= 3

        info["file_links_found"] = file_count
        info["product_links_found"] = product_count
        info["has_pagination"] = has_pagination
        info["relevance_hits"] = relevance_hits

        # Determine mode
        if product_count >= 10 or has_pagination:
            info["mode"] = "web"
        elif file_count >= 3:
            info["mode"] = "files"
        elif product_count >= 3 and file_count >= 1:
            info["mode"] = "web"  # likely a mixed catalogue
        else:
            info["mode"] = "unknown"

        return info

    except Exception as error:
        info["status"] = f"error: {error}"
        return info


def _dedup_by_domain(candidates: List[Dict]) -> List[Dict]:
    """Keep highest-scored URL per domain, aggregate scores."""
    by_domain: Dict[str, List[Dict]] = defaultdict(list)
    for item in candidates:
        by_domain[item["domain"]].append(item)

    deduped = []
    for domain, items in by_domain.items():
        items.sort(key=lambda x: x["score"], reverse=True)
        best = items[0].copy()
        if len(items) > 1:
            # Sum scores from other URLs on the same domain
            extra_score = sum(it["score"] for it in items[1:])
            best["score"] += extra_score // 2  # partial credit for other URLs
            best["domain_urls_found"] = len(items)
        else:
            best["domain_urls_found"] = 1
        deduped.append(best)

    return deduped


def discover_sources(
    queries: List[str],
    profile: Dict,
    profile_name: str,
    research_sources: List[str],
    limit_per_query: int,
    top_n: int,
    probe: bool,
    engine: str = "yandex",
) -> Dict:
    seen: Dict[str, Dict] = {}
    max_seed_sources = 200

    for idx, query in enumerate(queries):
        print(f"  [{idx + 1}/{len(queries)}] Searching: {query[:60]}...")
        results = []

        if engine in ("yandex", "both"):
            results = _search_with_retry(search_yandex, query, limit_per_query)
            if results:
                provider = "yandex"

        if not results and engine in ("google", "both"):
            results = _search_with_retry(search_google, query, limit_per_query)
            if results:
                provider = "google"

        if engine == "both" and results:
            # For "both" mode, also try the other engine
            provider = "yandex+google"
            other = _search_with_retry(
                search_google if provider.startswith("yandex") else search_yandex,
                query, limit_per_query,
            )
            results = list(dict.fromkeys(results + other))  # dedup preserving order

        if not results:
            print("    No results for this query")
            continue

        print(f"    Found {len(results)} results")

        for url in results:
            domain = _domain(url)
            if not domain or domain in DENY_DOMAINS:
                continue
            s = score_candidate(url, profile)
            existing = seen.get(url)
            if existing:
                existing["score"] += s
                existing["queries"].append(query)
            else:
                seen[url] = {
                    "url": url,
                    "domain": domain,
                    "score": s,
                    "queries": [query],
                }

    # Research seeds
    if research_sources:
        print(f"  Adding {len(research_sources[:max_seed_sources])} research seeds...")
        for seed_url in research_sources[:max_seed_sources]:
            domain = _domain(seed_url)
            if not domain or domain in DENY_DOMAINS:
                continue
            boost = 35
            if any(h in domain for h in profile["priority_domains"]):
                boost += 15
            existing = seen.get(seed_url)
            if existing:
                existing["score"] += boost
                existing["queries"].append("research_seed")
            else:
                seen[seed_url] = {
                    "url": seed_url,
                    "domain": domain,
                    "score": score_candidate(seed_url, profile) + boost,
                    "queries": ["research_seed"],
                }

    candidates = list(seen.values())

    # Domain-level dedup before probing (saves probe requests)
    candidates = _dedup_by_domain(candidates)

    # Sort and limit before probing for speed
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:max(top_n * 3, 40)]

    if probe:
        print(f"  Probing {len(candidates)} candidates...")
    for idx, item in enumerate(candidates):
        if probe:
            if (idx + 1) % 10 == 0 or idx == 0:
                print(f"    [{idx + 1}/{len(candidates)}] probing...")
            probe_data = probe_source(item["url"], profile)
            item.update(probe_data)
            item["score"] += min(item.get("file_links_found", 0), 20)
            item["score"] += min(item.get("product_links_found", 0) // 2, 15)
            item["score"] += min(item.get("relevance_hits", 0), 12)
            if item.get("has_pagination"):
                item["score"] += 10
            if item.get("status", "").startswith("error"):
                item["score"] -= 8
        else:
            item["file_links_found"] = 0
            item["product_links_found"] = 0
            item["has_pagination"] = False
            item["relevance_hits"] = 0
            item["mode"] = "unknown"
            item["status"] = "not_probed"

        item["queries"] = sorted(set(item["queries"]))

    candidates = [item for item in candidates if item["score"] >= 12]
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:top_n]

    for idx, item in enumerate(candidates):
        item["rank"] = idx + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile_name,
        "queries": queries,
        "engine": engine,
        "research_seed_count": len(research_sources),
        "total_candidates": len(candidates),
        "candidates": candidates,
    }


def main() -> None:
    available = _list_profiles()
    parser = argparse.ArgumentParser(
        description="Discover candidate websites to scrape",
    )
    parser.add_argument(
        "--profile", default="electrical",
        help=f"Industry profile name (available: {', '.join(available)})",
    )
    parser.add_argument("--research", default=None, metavar="FILE",
                        help="Path to research document with seed URLs (optional)")
    parser.add_argument("--limit-per-query", type=int, default=20)
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--out", default=None, metavar="FILE",
                        help="Candidates output (default: discovery/sources_candidates.json)")
    parser.add_argument("--approved-out", default=None, metavar="FILE",
                        help="Approved template output (default: discovery/sources_approved.json)")
    parser.add_argument("--query", action="append", default=[],
                        help="Custom search query (repeatable, overrides profile queries)")
    parser.add_argument("--probe", action="store_true",
                        help="Probe pages for content type detection (slower)")
    parser.add_argument("--engine", choices=["yandex", "google", "both"],
                        default="yandex", help="Search engine to use (default: yandex)")
    args = parser.parse_args()

    profile = _load_profile(args.profile)
    queries = args.query or profile["queries"]

    research_sources = []
    if args.research:
        research_sources = extract_research_sources(args.research)
        print(f"Loaded {len(research_sources)} research seeds from {args.research}")

    os.makedirs(os.path.abspath(DISCOVERY_DIR), exist_ok=True)
    out_path = args.out or os.path.join(
        os.path.abspath(DISCOVERY_DIR), "sources_candidates.json"
    )
    approved_path = args.approved_out or os.path.join(
        os.path.abspath(DISCOVERY_DIR), "sources_approved.json"
    )

    print(f"Profile: {args.profile}")
    print(f"Engine: {args.engine}")
    print(f"Queries: {len(queries)}")
    print(f"Probe: {'yes' if args.probe else 'no'}")
    print()

    report = discover_sources(
        queries=queries,
        profile=profile,
        profile_name=args.profile,
        research_sources=research_sources,
        limit_per_query=args.limit_per_query,
        top_n=args.top_n,
        probe=args.probe,
        engine=args.engine,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    approved_payload = {
        "generated_at": report["generated_at"],
        "profile": args.profile,
        "notes": "Set approved=true for allowed sources, then use this file as input for scraping.",
        "sources": [
            {
                "url": item["url"],
                "domain": item["domain"],
                "mode": item.get("mode", "unknown"),
                "approved": False,
                "priority": item["rank"],
                "score": item["score"],
            }
            for item in report["candidates"]
        ],
    }

    with open(approved_path, "w", encoding="utf-8") as f:
        json.dump(approved_payload, f, ensure_ascii=False, indent=2)

    print(f"\nDone: {report['total_candidates']} candidates")
    print(f"  Saved candidates: {out_path}")
    print(f"  Saved review template: {approved_path}")

    # Summary of modes detected
    if args.probe:
        modes = defaultdict(int)
        for c in report["candidates"]:
            modes[c.get("mode", "unknown")] += 1
        print(f"  Modes: {dict(modes)}")


if __name__ == "__main__":
    main()
