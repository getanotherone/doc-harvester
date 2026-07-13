"""Playwright-based browser for fetching pages that block requests-based crawlers.

Usage:
    from browser import browser_fetch

    html = browser_fetch("https://example.com/catalog/item")

The browser launches lazily on first call and reuses a single context
for the entire process lifetime. Cleanup happens via atexit.
"""

import atexit
import json
import os
import re
import time
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

_playwright = None
_browser: Browser | None = None
_context: BrowserContext | None = None

# Stealth settings
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

BROWSER_TIMEOUT_MS = int(os.environ.get("BROWSER_TIMEOUT_MS", "30000"))
# Restart browser every N fetches to release leaked memory.
# Chrome accumulates ~2-5 MB per page that never gets freed.
# At 200 pages that's ~0.5-1 GB — restart brings it back to baseline (~400 MB).
BROWSER_RECYCLE_INTERVAL = int(os.environ.get("BROWSER_RECYCLE_INTERVAL", "200"))
_fetch_count = 0
# Use system Chrome instead of bundled Chromium for better anti-bot stealth.
# chrome = real TLS fingerprint, plugins, WebGL — passes most bot detectors.
# Set BROWSER_CHANNEL="" to fall back to bundled Chromium.
BROWSER_CHANNEL = os.environ.get("BROWSER_CHANNEL", "chrome")
# Path to saved browser cookies/storage (created by `python3 browser.py --save-session`)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROWSER_STATE_PATH = os.environ.get("BROWSER_STATE_PATH", os.path.join(_PROJECT_ROOT, "data", "browser_state.json"))


def _maybe_recycle() -> None:
    """Restart browser if fetch count exceeded the recycle interval.

    Chrome leaks ~2-5 MB per page load that never gets garbage-collected.
    After 200 pages, that's 0.5-1 GB of wasted RAM. Recycling kills the
    Chrome process and starts a fresh one — takes ~2 seconds, saves gigabytes.
    """
    global _fetch_count
    if BROWSER_RECYCLE_INTERVAL <= 0:
        return
    if _context is None:
        return
    if _fetch_count < BROWSER_RECYCLE_INTERVAL:
        return
    print(f"  browser: recycling after {_fetch_count} fetches (memory cleanup)")
    _restart_browser()
    _fetch_count = 0


def _ensure_browser() -> BrowserContext:
    """Launch browser and context if not already running."""
    global _playwright, _browser, _context
    if _context is not None:
        return _context

    _playwright = sync_playwright().start()
    launch_kwargs = {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    }
    if BROWSER_CHANNEL:
        launch_kwargs["channel"] = BROWSER_CHANNEL
    _browser = _playwright.chromium.launch(**launch_kwargs)
    context_kwargs = {
        "user_agent": _USER_AGENT,
        "viewport": {"width": 1920, "height": 1080},
        "locale": "ru-RU",
        "timezone_id": "Europe/Moscow",
        "java_script_enabled": True,
    }
    # Load saved cookies/session if available (from --save-session)
    if os.path.exists(BROWSER_STATE_PATH):
        context_kwargs["storage_state"] = BROWSER_STATE_PATH
    _context = _browser.new_context(**context_kwargs)
    # Remove webdriver flag
    _context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)
    atexit.register(_cleanup)
    return _context


def _cleanup():
    """Shut down browser on process exit."""
    global _playwright, _browser, _context
    try:
        if _context:
            _context.close()
        if _browser:
            _browser.close()
        if _playwright:
            _playwright.stop()
    except Exception:
        pass
    _context = None
    _browser = None
    _playwright = None


def _restart_browser() -> BrowserContext:
    """Kill crashed browser and launch a fresh one.

    Called when browser_fetch/browser_fetch_rendered catches a fatal browser
    error (Target page closed, Connection closed, Protocol error).
    """
    global _playwright, _browser, _context
    print("  browser: restarting crashed browser...")
    try:
        if _context:
            _context.close()
    except Exception:
        pass
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    try:
        if _playwright:
            _playwright.stop()
    except Exception:
        pass
    _context = None
    _browser = None
    _playwright = None
    return _ensure_browser()


def _is_browser_dead(error: Exception) -> bool:
    """Check if the error indicates the browser process has crashed/closed."""
    msg = str(error).lower()
    return any(phrase in msg for phrase in (
        "target page, context or browser has been closed",
        "browser has been closed",
        "connection closed",
        "protocol error",
        "browser closed",
        "crashed",
    ))


class PageContent:
    """Result of a browser fetch — carries both raw HTML and rendered text."""
    __slots__ = ("html", "rendered_text")

    def __init__(self, html: str, rendered_text: str = ""):
        self.html = html
        self.rendered_text = rendered_text


# Extra wait (ms) for SPA sites to finish rendering after domcontentloaded
SPA_RENDER_WAIT_MS = int(os.environ.get("SPA_RENDER_WAIT_MS", "3000"))


def browser_fetch(url: str, wait_until: str = "domcontentloaded") -> str | None:
    """Fetch a page using Playwright and return its HTML.

    Returns HTML string on success, None on failure.
    Does NOT handle retries or 429 — that's the caller's job.
    Auto-restarts the browser if it has crashed and retries once.
    """
    global _fetch_count
    _maybe_recycle()
    _fetch_count += 1
    for _attempt in range(2):  # at most one restart
        context = _ensure_browser()
        page = None
        try:
            page = context.new_page()
            response = page.goto(url, wait_until=wait_until, timeout=BROWSER_TIMEOUT_MS)
            if response is None:
                return None
            status = response.status
            if status == 429:
                raise _Rate429(f"429 on {url}")
            if status == 404:
                raise _Http404(f"404 on {url}")
            if status >= 400:
                print(f"  browser: HTTP {status} on {url}")
                return None
            # Wait a bit for JS-rendered content to settle
            page.wait_for_timeout(1500)
            html = page.content()
            captcha_type = detect_captcha(html)
            if captcha_type:
                raise _CaptchaDetected(f"CAPTCHA ({captcha_type}) on {url}")
            return html
        except (_Rate429, _Http404, _CaptchaDetected):
            raise
        except Exception as e:
            if _is_browser_dead(e) and _attempt == 0:
                print(f"  browser: error fetching {url}: {e}")
                try:
                    if page:
                        page.close()
                except Exception:
                    pass
                _restart_browser()
                continue  # retry with fresh browser
            print(f"  browser: error fetching {url}: {e}")
            return None
        finally:
            try:
                if page:
                    page.close()
            except Exception:
                pass
    return None


def browser_fetch_rendered(url: str) -> PageContent | None:
    """Fetch a page and return both HTML and rendered inner text.

    For SPA sites where content is rendered by JS frameworks (React, Vue, etc.),
    the raw HTML may contain empty divs. This function waits longer for JS to
    settle, clicks spec/detail tabs if found, and extracts inner_text().

    Returns PageContent on success, None on failure.
    Raises _Rate429 / _Http404 like browser_fetch.
    Auto-restarts the browser if it has crashed and retries once.
    """
    global _fetch_count
    _maybe_recycle()
    _fetch_count += 1
    for _attempt in range(2):  # at most one restart
        context = _ensure_browser()
        page = None
        try:
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=BROWSER_TIMEOUT_MS)
            if response is None:
                return None
            status = response.status
            if status == 429:
                raise _Rate429(f"429 on {url}")
            if status == 404:
                raise _Http404(f"404 on {url}")
            if status >= 400:
                print(f"  browser: HTTP {status} on {url}")
                return None

            # Wait for SPA frameworks to hydrate
            page.wait_for_timeout(SPA_RENDER_WAIT_MS)

            # Try clicking specs/characteristics tabs to reveal hidden content
            _click_spec_tabs(page)

            html = page.content()
            captcha_type = detect_captcha(html)
            if captcha_type:
                raise _CaptchaDetected(f"CAPTCHA ({captcha_type}) on {url}")
            rendered_text = page.inner_text("body")
            return PageContent(html, rendered_text)
        except (_Rate429, _Http404, _CaptchaDetected):
            raise
        except Exception as e:
            if _is_browser_dead(e) and _attempt == 0:
                print(f"  browser: error fetching {url}: {e}")
                try:
                    if page:
                        page.close()
                except Exception:
                    pass
                _restart_browser()
                continue  # retry with fresh browser
            print(f"  browser: error fetching {url}: {e}")
            return None
        finally:
            try:
                if page:
                    page.close()
            except Exception:
                pass
    return None


# Tab labels that commonly hide product specifications
_SPEC_TAB_LABELS = [
    "характеристики", "specifications", "спецификации",
    "детали", "details", "параметры", "описание",
]


def _dismiss_cookie_popup(page: Page) -> None:
    """Dismiss cookie consent popups that block clicks on page elements."""
    try:
        for selector in [
            'button:has-text("принять")', 'button:has-text("согласен")',
            'button:has-text("accept")', 'button:has-text("OK")',
            '[class*="cookie"] button', '[class*="consent"] button',
            '[class*="cookie_popup"] button', '[class*="cookie"] a',
        ]:
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=300):
                    el.click(timeout=800)
                    page.wait_for_timeout(300)
                    return
            except Exception:
                continue
        # Fallback: try to hide the popup via JS
        page.evaluate("""
            document.querySelectorAll('[class*="cookie_popup"], [class*="cookie-banner"], [class*="consent"]')
                .forEach(el => el.style.display = 'none');
        """)
    except Exception:
        pass


def _click_spec_tabs(page: Page) -> None:
    """Click on tabs that might reveal hidden spec/detail content.

    Searches for clickable elements whose text matches common spec labels.
    Uses two strategies:
    1. Standard selectors (button, [role=tab], a, li)
    2. Generic divs/spans — but filters to short-text elements to avoid
       clicking large container divs that happen to contain the word.
    """
    try:
        _dismiss_cookie_popup(page)
        for label in _SPEC_TAB_LABELS:
            # Strategy 1: standard clickable elements
            try:
                el = page.locator(
                    f'button:has-text("{label}"), '
                    f'[role="tab"]:has-text("{label}"), '
                    f'a:has-text("{label}"), '
                    f'li:has-text("{label}")'
                ).first
                if el.is_visible(timeout=300):
                    el.click(timeout=800)
                    page.wait_for_timeout(500)
                    return
            except Exception:
                pass
            # Strategy 2: div/span tabs (e.g. elektro.ru uses div as tab triggers)
            # Filter to elements whose own text is short (actual tab label, not a container)
            try:
                candidates = page.locator(
                    f'div:has-text("{label}"), span:has-text("{label}")'
                )
                for i in range(min(candidates.count(), 10)):
                    el = candidates.nth(i)
                    try:
                        if not el.is_visible(timeout=200):
                            continue
                        text = el.inner_text(timeout=200).strip()
                        # Only click if the element's text is just the label (not a big container)
                        if len(text) < 30 and label in text.lower():
                            el.click(timeout=800)
                            page.wait_for_timeout(500)
                            return
                    except Exception:
                        continue
            except Exception:
                pass
    except Exception:
        pass  # tab clicking is best-effort


class _Rate429(Exception):
    """Internal signal for 429 status — re-raised as RateLimitError by caller."""
    pass


class _Http404(Exception):
    """Internal signal for 404 status — caller uses for dead-URL tracking."""
    pass


class _CaptchaDetected(Exception):
    """Internal signal when fetched page is a CAPTCHA challenge, not real content."""
    pass


# Patterns that indicate a CAPTCHA challenge page
_CAPTCHA_PATTERNS = [
    # reCAPTCHA
    (re.compile(r'google\.com/recaptcha', re.IGNORECASE), "recaptcha"),
    (re.compile(r'class=["\']g-recaptcha["\']', re.IGNORECASE), "recaptcha"),
    # Yandex SmartCaptcha
    (re.compile(r'smartcaptcha\.yandexcloud', re.IGNORECASE), "yandex_smartcaptcha"),
    (re.compile(r'id=["\']smartcaptcha["\']', re.IGNORECASE), "yandex_smartcaptcha"),
    # Generic challenge pages
    (re.compile(r'class=["\'][^"\']*captcha-container', re.IGNORECASE), "captcha"),
    (re.compile(r'class=["\'][^"\']*challenge-platform', re.IGNORECASE), "captcha"),
]


def detect_captcha(html: str) -> str | None:
    """Check if HTML is a CAPTCHA challenge page. Returns captcha type or None."""
    if not html:
        return None
    for pattern, captcha_type in _CAPTCHA_PATTERNS:
        if pattern.search(html):
            # Avoid false positives: reCAPTCHA scripts can be on real pages.
            # A true challenge page has very little body text.
            body_match = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
            if body_match:
                # Strip tags to get visible text length
                body_text = re.sub(r'<[^>]+>', '', body_match.group(1)).strip()
                if len(body_text) < 500:
                    return captcha_type
    return None


def save_session(urls: list[str]) -> None:
    """Open a headed browser, navigate to URLs so you can solve CAPTCHAs,
    then save cookies to BROWSER_STATE_PATH for headless reuse.

    Usage: python3 browser.py --save-session https://cable.ru/cable/ https://petrovich.ru/catalog/1384/

    The browser stays open until you press Enter in the terminal for EACH url.
    Take your time — solve CAPTCHAs, click anti-bot buttons, browse a few pages
    to build up a realistic cookie/session profile.
    """
    pw = sync_playwright().start()
    launch_kwargs = {
        "headless": False,
        "slow_mo": 100,  # Slow down actions so anti-bot doesn't flag instant clicks
        "args": ["--no-sandbox"],
    }
    if BROWSER_CHANNEL:
        launch_kwargs["channel"] = BROWSER_CHANNEL
    br = pw.chromium.launch(**launch_kwargs)

    # Load existing state if present (keeps valid cookies for other domains)
    context_kwargs = {
        "user_agent": _USER_AGENT,
        "viewport": {"width": 1920, "height": 1080},
        "locale": "ru-RU",
        "timezone_id": "Europe/Moscow",
    }
    if os.path.exists(BROWSER_STATE_PATH):
        context_kwargs["storage_state"] = BROWSER_STATE_PATH
        print(f"Loaded existing session from {BROWSER_STATE_PATH}")

    ctx = br.new_context(**context_kwargs)
    ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    for url in urls:
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"  Navigation error (may be fine): {e}")
        print(f"\n  Opened: {url}")
        print("  >>> Solve CAPTCHA / anti-bot check, browse a few pages <<<")
        print("  >>> Then press Enter here when done with this site...  <<<")
        input()

    ctx.storage_state(path=BROWSER_STATE_PATH)
    print(f"\nSession saved to {BROWSER_STATE_PATH}")
    ctx.close()
    br.close()
    pw.stop()


_CAPTCHA_DOMAINS = ["cable.ru", "petrovich.ru", "ekfgroup.com", "ruscable.ru", "elcable.ru"]

# Map each CAPTCHA domain to a URL we visit to refresh cookies
_CAPTCHA_URLS = {
    "cable.ru": "https://cable.ru/cable/",
    "petrovich.ru": "https://petrovich.ru/catalog/1384/",
    "ekfgroup.com": "https://ekfgroup.com/ru/catalog/",
    "ruscable.ru": "https://www.ruscable.ru/info/cable/",
    "elcable.ru": "https://www.elcable.ru/",
}


def refresh_expired_sessions() -> dict:
    """Try to auto-refresh expired cookies by visiting each site headlessly.

    Opens a headless browser with the existing saved state, visits each expired
    domain's page, waits for it to load, then saves cookies back.  If the site
    serves a CAPTCHA instead of normal content, the refresh won't help — but it
    costs nothing to try.

    Returns {domain: "refreshed"|"captcha"|"failed"|"skipped"} for each CAPTCHA domain.
    """
    staleness = check_session_staleness()
    expired = [d for d, info in staleness.items() if info["status"] in ("expired", "missing")]
    if not expired:
        return {d: "skipped" for d in _CAPTCHA_DOMAINS}

    pw = sync_playwright().start()
    launch_kwargs = {"headless": True, "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox"]}
    if BROWSER_CHANNEL:
        launch_kwargs["channel"] = BROWSER_CHANNEL
    br = pw.chromium.launch(**launch_kwargs)

    # Load existing state if present (keeps valid cookies for non-expired domains)
    ctx_kwargs = {
        "user_agent": _USER_AGENT,
        "viewport": {"width": 1920, "height": 1080},
        "locale": "ru-RU",
        "timezone_id": "Europe/Moscow",
    }
    if os.path.exists(BROWSER_STATE_PATH):
        ctx_kwargs["storage_state"] = BROWSER_STATE_PATH
    ctx = br.new_context(**ctx_kwargs)
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")

    results = {}
    for domain in _CAPTCHA_DOMAINS:
        if domain not in expired:
            results[domain] = "skipped"
            continue

        url = _CAPTCHA_URLS.get(domain, f"https://{domain}/")
        try:
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)  # let cookies settle

            # Check if we got a CAPTCHA page instead of real content
            body_text = page.inner_text("body")[:500].lower()
            is_captcha = any(kw in body_text for kw in ["captcha", "recaptcha", "robot", "проверка"])

            page.close()
            if is_captcha:
                results[domain] = "captcha"
                print(f"  {domain}: CAPTCHA detected — manual refresh needed")
            else:
                results[domain] = "refreshed"
                print(f"  {domain}: auto-refreshed")
        except Exception as e:
            results[domain] = "failed"
            print(f"  {domain}: refresh failed — {e}")

    # Save updated cookies (includes fresh cookies from visited sites)
    ctx.storage_state(path=BROWSER_STATE_PATH)
    ctx.close()
    br.close()
    pw.stop()

    return results


def check_session_staleness() -> dict:
    """Check if saved browser session cookies are still valid for CAPTCHA domains.

    Returns {domain: {"status": "ok"|"expired"|"expiring_soon"|"missing", "detail": str}}
    """
    if not os.path.exists(BROWSER_STATE_PATH):
        return {d: {"status": "missing", "detail": "no browser_state.json"} for d in _CAPTCHA_DOMAINS}

    with open(BROWSER_STATE_PATH, "r") as f:
        state = json.load(f)

    cookies = state.get("cookies", [])
    now = time.time()
    two_days = 2 * 86400

    result = {}
    for domain in _CAPTCHA_DOMAINS:
        # Find persistent cookies for this domain (skip session cookies with expires <= 0)
        domain_cookies = [
            c for c in cookies
            if domain in c.get("domain", "") and c.get("expires", -1) > 0
        ]
        if not domain_cookies:
            result[domain] = {"status": "expired", "detail": "no persistent cookies found"}
            continue

        earliest = min(c["expires"] for c in domain_cookies)
        if earliest < now:
            result[domain] = {"status": "expired", "detail": f"cookies expired {int((now - earliest) / 86400)}d ago"}
        elif earliest - now < two_days:
            hours_left = int((earliest - now) / 3600)
            result[domain] = {"status": "expiring_soon", "detail": f"expires in {hours_left}h"}
        else:
            days_left = int((earliest - now) / 86400)
            result[domain] = {"status": "ok", "detail": f"valid for {days_left}d"}

    return result


if __name__ == "__main__":
    import sys
    if "--save-session" in sys.argv:
        urls = [a for a in sys.argv[1:] if a != "--save-session"]
        if not urls:
            urls = [
                "https://cable.ru/cable/",
                "https://ekfgroup.com/ru/catalog/",
                "https://www.ruscable.ru/info/cable/",
                "https://www.elcable.ru/",
            ]
        save_session(urls)
    else:
        print("Usage: python3 browser.py --save-session [URL1 URL2 ...]")
        print("  Opens a visible browser so you can solve CAPTCHAs.")
        print("  Saves cookies to browser_state.json for headless reuse.")
