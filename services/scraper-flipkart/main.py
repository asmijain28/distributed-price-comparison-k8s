"""
PriceRadar v2 — Flipkart Scraper Microservice
================================================
EDUCATIONAL / ACADEMIC USE ONLY

Scraping approach
-----------------
GET https://www.flipkart.com/search?marketplace=FLIPKART&q=<query>
Flipkart renders product cards as div[data-id] in SSR HTML.

Selectors (verified March 2026):
  Cards  : div[data-id]
  Title  : first img[alt]
  Price  : all ₹-prefixed text nodes → min value = selling price
  Image  : first img[src]
  URL    : first a[href]  (relative, prepend BASE_URL)
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.schemas import ProductResult
from common.scraper_utils import (
    build_client,
    fetch_with_retry,
    get_default_headers,
    polite_delay,
)

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("priceradar.scraper.flipkart")

app = FastAPI(title="PriceRadar — Flipkart Scraper", version="3.0.0")

BASE_URL = "https://www.flipkart.com"
SEARCH_URL = f"{BASE_URL}/search"
PLATFORM = "Flipkart"
PLATFORM_LOGO = "🏷️"


def _extract_price(card: Tag) -> Optional[float]:
    """Collect all ₹-prefixed text nodes, return the minimum (= selling price)."""
    prices: list[float] = []
    for tag in card.find_all(True):
        t = tag.get_text(strip=True)
        if t.startswith("₹"):
            raw = t.replace("₹", "").replace(",", "").strip()
            try:
                prices.append(float(raw))
            except ValueError:
                pass
    return min(prices) if prices else None


def _extract_title(card: Tag) -> Optional[str]:
    img = card.select_one("img")
    if img:
        return img.get("alt", "").strip() or None
    return None


def _extract_url(card: Tag) -> Optional[str]:
    a = card.select_one("a[href]")
    if a:
        href = a.get("href", "")
        if href.startswith("http"):
            return href
        if href:
            return BASE_URL + href
    return None


def _extract_image(card: Tag) -> Optional[str]:
    img = card.select_one("img[src]")
    return img.get("src") if img else None


def _extract_rating(card: Tag) -> Optional[float]:
    # Flipkart rating divs use frequently-changing class names;
    # fall back to scanning for a standalone float like "4.3"
    for tag in card.find_all(True):
        t = tag.get_text(strip=True)
        m = re.fullmatch(r"[1-5]\.[0-9]", t)
        if m:
            try:
                val = float(t)
                if 1.0 <= val <= 5.0:
                    return val
            except ValueError:
                pass
    return None


@app.get("/search", response_model=list[ProductResult])
async def search(q: str = Query(..., min_length=1)):
    logger.info("Searching Flipkart for: %s", q)
    await polite_delay()

    headers = get_default_headers(referer=BASE_URL)
    params = {"marketplace": "FLIPKART", "q": q}

    async with build_client() as client:
        resp = await fetch_with_retry(client, SEARCH_URL, headers=headers, params=params, max_retries=0)

    if resp is None:
        logger.warning("Failed to fetch Flipkart results for '%s'", q)
        return JSONResponse(content=[], status_code=200)

    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select("div[data-id]")
    logger.info("Found %d Flipkart product cards", len(cards))

    results: list[ProductResult] = []
    for card in cards:
        try:
            title = _extract_title(card)
            if not title:
                continue

            price = _extract_price(card)
            if price is None or price <= 0:
                continue

            url = _extract_url(card) or BASE_URL
            image_url = _extract_image(card)
            rating = _extract_rating(card)

            results.append(
                ProductResult(
                    title=title[:200],
                    price=price,
                    platform=PLATFORM,
                    platform_logo=PLATFORM_LOGO,
                    url=url,
                    image_url=image_url,
                    rating=rating,
                    availability="In Stock",
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        except Exception:
            logger.exception("Error parsing a Flipkart product card")
            continue

    logger.info("Returning %d results from Flipkart", len(results))
    return results


@app.get("/health")
async def health():
    return {"status": "healthy", "platform": PLATFORM, "mode": "live"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
