"""
PriceRadar v2 — Shared Scraper Utilities
==========================================
Common helpers used by all scraper microservices:
  - Rotating User-Agent pool
  - Async HTTP client factory with retry logic
  - Configurable request throttling
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Optional

import httpx

logger = logging.getLogger("priceradar.scraper_utils")

# ---------------------------------------------------------------------------
# Rotating User-Agent strings (real Chrome / Safari on Windows / macOS / Linux)
# ---------------------------------------------------------------------------
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]


def get_random_ua() -> str:
    """Return a random User-Agent string from the pool."""
    return random.choice(USER_AGENTS)


def get_default_headers(referer: Optional[str] = None) -> dict[str, str]:
    """Build standard headers that mimic a real browser request."""
    headers = {
        "User-Agent": get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if referer:
        headers["Referer"] = referer
    return headers


# ---------------------------------------------------------------------------
# Configurable delay & timeout from environment
# ---------------------------------------------------------------------------
SCRAPE_DELAY_MS: int = int(os.getenv("SCRAPE_DELAY_MS", "500"))
SCRAPE_TIMEOUT_SECONDS: int = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "8"))


async def polite_delay() -> None:
    """Async sleep for the configured scrape delay — be polite to target servers."""
    await asyncio.sleep(SCRAPE_DELAY_MS / 1000.0)


def build_client(**kwargs) -> httpx.AsyncClient:
    """Create an httpx AsyncClient with sensible defaults for scraping."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(SCRAPE_TIMEOUT_SECONDS, connect=5.0),
        follow_redirects=True,
        http2=True,
        **kwargs,
    )


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: Optional[dict] = None,
    max_retries: int = 1,
    params: Optional[dict] = None,
) -> Optional[httpx.Response]:
    """
    Fetch a URL with retry on 429/503.

    On transient failure, waits ``SCRAPE_DELAY_MS * 2`` then retries once.
    Returns ``None`` if all attempts fail.
    """
    _headers = headers or get_default_headers()
    for attempt in range(1 + max_retries):
        try:
            resp = await client.get(url, headers=_headers, params=params)
            if resp.status_code in (429, 503) and attempt < max_retries:
                wait = (SCRAPE_DELAY_MS * 2) / 1000.0
                logger.warning(
                    "Got %d from %s — retrying in %.1fs (attempt %d/%d)",
                    resp.status_code,
                    url,
                    wait,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as exc:
            logger.error("HTTP error fetching %s: %s", url, exc)
            return None
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            logger.error("Request error fetching %s: %s", url, exc)
            if attempt < max_retries:
                await asyncio.sleep((SCRAPE_DELAY_MS * 2) / 1000.0)
                continue
            return None
    return None
