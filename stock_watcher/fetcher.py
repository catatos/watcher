from __future__ import annotations

import os
import time
from urllib.parse import urlparse
import urllib.error
import urllib.request


class FetchError(Exception):
    pass


class BlockedError(FetchError):
    pass


def _parse_cookie_header(cookie_header: str) -> list[dict[str, str | bool]]:
    cookies: list[dict[str, str | bool]] = []
    parts = cookie_header.split(";")
    for part in parts:
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "path": "/",
                "httpOnly": False,
                "secure": True,
            }
        )
    return cookies


def _fetch_url_playwright(
    url: str,
    timeout_s: int = 30,
    extra_headers: dict[str, str] | None = None,
) -> str:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ModuleNotFoundError as exc:
        raise FetchError(
            "Playwright is not installed. Install with: "
            "`python3 -m pip install playwright && python3 -m playwright install chromium`"
        ) from exc

    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    timeout_ms = int(timeout_s * 1000)

    parsed = urlparse(url)
    domain = parsed.hostname or ""

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-dev-shm-usage",
            ],
        )
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/Los_Angeles",
                viewport={"width": 1440, "height": 900},
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )

            headers = dict(extra_headers or {})
            cookie_header = headers.pop("Cookie", None)
            if headers:
                context.set_extra_http_headers(headers)

            if cookie_header and domain:
                cookies = _parse_cookie_header(cookie_header)
                for c in cookies:
                    c["domain"] = domain
                if cookies:
                    context.add_cookies(cookies)

            page = context.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            status = resp.status if resp is not None else None

            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                pass

            html = page.content()
            lower = html.lower()

            if status in (403, 429):
                # Some anti-bot pages report 403 first; treat as blocked only if
                # rendered content still looks like a challenge page.
                blocked_markers = [
                    "attention required",
                    "cloudflare",
                    "cf-chl",
                    "captcha",
                    "access denied",
                ]
                if any(marker in lower for marker in blocked_markers):
                    raise BlockedError(f"HTTP {status} while fetching {url}")

            return html
        finally:
            browser.close()


def fetch_url(
    url: str,
    timeout_s: int = 15,
    retries: int = 3,
    backoff_s: float = 1.0,
    extra_headers: dict[str, str] | None = None,
    strategy: str = "urllib",
) -> str:
    strategy = strategy.lower().strip()
    if strategy == "playwright":
        return _fetch_url_playwright(
            url=url,
            timeout_s=max(15, timeout_s),
            extra_headers=extra_headers,
        )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra_headers:
        headers.update(extra_headers)

    last_exc: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                code = getattr(resp, "status", 200)
                if code in (403, 429):
                    raise BlockedError(f"HTTP {code} while fetching {url}")
                body = resp.read()
                return body.decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                raise BlockedError(f"HTTP {exc.code} while fetching {url}") from exc
            last_exc = exc
        except (urllib.error.URLError, TimeoutError, FetchError) as exc:
            last_exc = exc

        if attempt < retries - 1:
            time.sleep(backoff_s * (2**attempt))

    raise FetchError(f"Failed to fetch {url}: {last_exc}")
