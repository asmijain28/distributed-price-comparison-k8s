"""
PriceRadar v2 — Amazon India Scraper Microservice
====================================================
Live HTTP scraper for amazon.in search results.

EDUCATIONAL / ACADEMIC USE ONLY
--------------------------------
This scraper is built for an academic distributed-systems project at
Manipal University Jaipur.  In production, you should use the official
Amazon Product Advertising API (PA-API 5.0) or a licensed data feed.
Scraping amazon.in may violate Amazon's Terms of Service.

Scraping approach
-----------------
GET https://www.amazon.in/s?k=<query>&ref=nb_sb_noss
Parse `.s-result-item[data-asin]` cards using BeautifulSoup.
Extract: title, price (`.a-price-whole`), rating, image, product URL.

NOTE: Amazon actively rotates its HTML class names and may serve CAPTCHAs.
The selectors below were valid as of early 2025 but may need updating.
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

# ── Add parent dir so we can import shared modules ──────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.schemas import ProductResult  # noqa: E402
from common.scraper_utils import (  # noqa: E402
    build_client,
    fetch_with_retry,
    get_default_headers,
    polite_delay,
)

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("priceradar.scraper.amazon")

# ── FastAPI app ─────────────────────────────────────────────────────────
app = FastAPI(title="PriceRadar — Amazon India Scraper", version="2.0.0")

BASE_URL = "https://www.amazon.in"
SEARCH_URL = f"{BASE_URL}/s"
PLATFORM = "Amazon"
PLATFORM_LOGO = "🛒"


# ── Helpers ─────────────────────────────────────────────────────────────

def _extract_price(card: Tag) -> Optional[float]:
    """Extract numeric INR price from an Amazon product card."""
    # Primary: `.a-price-whole` holds the integer part (e.g., "1,299")
    el = card.select_one("span.a-price-whole")
    if el:
        raw = el.get_text(strip=True).replace(",", "").replace(".", "")
        try:
            return float(raw)
        except ValueError:
            pass
    # Fallback: look for `.a-price > .a-offscreen` which has the full "₹1,299.00"
    el = card.select_one("span.a-price span.a-offscreen")
    if el:
        raw = el.get_text(strip=True).replace("₹", "").replace(",", "").strip()
        try:
            return float(raw)
        except ValueError:
            pass
    return None


def _extract_rating(card: Tag) -> Optional[float]:
    """Extract star rating from Amazon card (e.g., '4.3 out of 5 stars')."""
    el = card.select_one("span.a-icon-alt")
    if el:
        m = re.search(r"([\d.]+)\s*out\s*of", el.get_text())
        if m:
            return float(m.group(1))
    return None


def _extract_review_count(card: Tag) -> Optional[int]:
    """Extract review count from the ratings link text (e.g., '12,345')."""
    # NOTE: selector targets the link wrapping the review count near rating stars
    el = card.select_one("span.a-size-base.s-underline-text")
    if el:
        raw = el.get_text(strip=True).replace(",", "")
        try:
            return int(raw)
        except ValueError:
            pass
    return None


def _extract_image(card: Tag) -> Optional[str]:
    """Extract product image URL from <img> tag inside `.s-image`."""
    img = card.select_one("img.s-image")
    if img:
        return img.get("src")
    return None


def _extract_title(card: Tag) -> Optional[str]:
    """Extract product title from the heading link."""
    # Primary selectors used by Amazon search results
    for sel in [
        "h2 a span",                       # most common
        "h2 span.a-text-normal",            # alternative
        "span.a-size-medium.a-color-base",  # fallback
    ]:
        el = card.select_one(sel)
        if el:
            title = el.get_text(strip=True)
            if title:
                return title
    return None


def _extract_url(card: Tag) -> Optional[str]:
    """Extract product detail page URL."""
    link = card.select_one("h2 a.a-link-normal")
    if link and link.get("href"):
        href = link["href"]
        if href.startswith("/"):
            return BASE_URL + href
        return href
    return None


# ── Search endpoint ─────────────────────────────────────────────────────

@app.get("/search", response_model=list[ProductResult])
async def search(q: str = Query(..., min_length=1, description="Search query")):
    """
    Search amazon.in for the given query and return normalised product results.
    """
    logger.info("Searching Amazon India for: %s", q)
    results: list[ProductResult] = []

    await polite_delay()

    headers = get_default_headers(referer=BASE_URL)
    params = {"k": q, "ref": "nb_sb_noss"}

    async with build_client() as client:
        resp = await fetch_with_retry(client, SEARCH_URL, headers=headers, params=params)

    if resp is None:
        logger.warning("Failed to fetch Amazon search results for '%s'", q)
        return JSONResponse(content=[], status_code=200)

    soup = BeautifulSoup(resp.text, "html.parser")

    # Each product card has `data-asin` attribute and class `s-result-item`
    cards = soup.select('div[data-asin][data-component-type="s-search-result"]')
    logger.info("Found %d Amazon product cards", len(cards))

    for card in cards:
        try:
            asin = card.get("data-asin", "")
            if not asin:
                continue

            title = _extract_title(card)
            if not title:
                continue

            price = _extract_price(card)
            if price is None or price <= 0:
                continue

            url = _extract_url(card) or f"{BASE_URL}/dp/{asin}"
            image_url = _extract_image(card)
            rating = _extract_rating(card)
            review_count = _extract_review_count(card)

            results.append(
                ProductResult(
                    title=title,
                    price=price,
                    platform=PLATFORM,
                    platform_logo=PLATFORM_LOGO,
                    url=url,
                    image_url=image_url,
                    rating=rating,
                    review_count=review_count,
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        except Exception:
            logger.exception("Error parsing an Amazon product card")
            continue

    logger.info("Returning %d results from Amazon India", len(results))
    return results


@app.get("/health")
async def health():
    return {"status": "healthy", "platform": PLATFORM, "mode": "live"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
