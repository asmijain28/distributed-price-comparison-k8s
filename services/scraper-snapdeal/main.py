"""
PriceRadar v2 — Snapdeal Scraper Microservice
===============================================
EDUCATIONAL / ACADEMIC USE ONLY

Scraping approach
-----------------
GET https://www.snapdeal.com/search?keyword=<query>&sort=rlvncy
Snapdeal uses server-side rendered HTML — all product cards are in
the initial response with no JS required.

Selectors (verified March 2026):
  Cards   : div.product-tuple-listing[data-isLive="true"]
  Title   : p.product-title  (text or title attribute)
  Price   : span.product-price[data-price]  (numeric attribute)
  Image   : img.product-image[src]
  URL     : a.dp-widget-link[href]
  Rating  : div.filled-stars[style]  (width % → stars out of 5)
  Reviews : p.product-rating-count   (text like "(1,234)")
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
logger = logging.getLogger("priceradar.scraper.snapdeal")

app = FastAPI(title="PriceRadar — Snapdeal Scraper", version="1.0.0")

BASE_URL = "https://www.snapdeal.com"
SEARCH_URL = f"{BASE_URL}/search"
PLATFORM = "Snapdeal"
PLATFORM_LOGO = "🔖"


def _extract_price(card: Tag) -> Optional[float]:
    el = card.select_one("span.product-price")
    if el:
        # Prefer the clean numeric data-price attribute
        data_price = el.get("data-price")
        if data_price:
            try:
                return float(data_price)
            except ValueError:
                pass
        # Fallback: parse "Rs. 1,299" text
        raw = el.get_text(strip=True).replace("Rs.", "").replace(",", "").strip()
        try:
            return float(raw)
        except ValueError:
            pass
    return None


def _extract_title(card: Tag) -> Optional[str]:
    el = card.select_one("p.product-title")
    if el:
        # title attribute is cleaner (avoids truncated text)
        return el.get("title") or el.get_text(strip=True) or None
    return None


def _extract_url(card: Tag) -> Optional[str]:
    el = card.select_one("a.dp-widget-link")
    if el:
        href = el.get("href", "")
        if href.startswith("http"):
            return href
        if href:
            return BASE_URL + href
    return None


def _extract_image(card: Tag) -> Optional[str]:
    img = card.select_one("img.product-image")
    if img:
        return img.get("src") or None
    return None


def _extract_rating(card: Tag) -> Optional[float]:
    el = card.select_one("div.filled-stars")
    if el:
        style = el.get("style", "")
        m = re.search(r"width:\s*([\d.]+)%", style)
        if m:
            # 100% = 5 stars, so divide by 20
            rating = round(float(m.group(1)) / 20, 1)
            if 0 < rating <= 5:
                return rating
    return None


def _extract_review_count(card: Tag) -> Optional[int]:
    el = card.select_one("p.product-rating-count")
    if el:
        m = re.search(r"[\d,]+", el.get_text())
        if m:
            try:
                return int(m.group().replace(",", ""))
            except ValueError:
                pass
    return None


@app.get("/search", response_model=list[ProductResult])
async def search(q: str = Query(..., min_length=1)):
    logger.info("Searching Snapdeal for: %s", q)
    await polite_delay()

    headers = get_default_headers(referer=BASE_URL)
    params = {"keyword": q, "sort": "rlvncy"}

    async with build_client() as client:
        resp = await fetch_with_retry(client, SEARCH_URL, headers=headers, params=params)

    if resp is None:
        logger.warning("Failed to fetch Snapdeal results for '%s'", q)
        return JSONResponse(content=[], status_code=200)

    soup = BeautifulSoup(resp.text, "lxml")
    cards = soup.select("div.product-tuple-listing")
    logger.info("Found %d Snapdeal product cards", len(cards))

    results: list[ProductResult] = []
    for card in cards:
        try:
            # Skip unavailable / non-live listings
            if card.get("data-isLive", "true").lower() != "true":
                continue

            title = _extract_title(card)
            if not title:
                continue

            price = _extract_price(card)
            if price is None or price <= 0:
                continue

            url = _extract_url(card) or BASE_URL
            image_url = _extract_image(card)
            rating = _extract_rating(card)
            review_count = _extract_review_count(card)

            results.append(
                ProductResult(
                    title=title[:200],
                    price=price,
                    platform=PLATFORM,
                    platform_logo=PLATFORM_LOGO,
                    url=url,
                    image_url=image_url,
                    rating=rating,
                    review_count=review_count,
                    availability="In Stock",
                    scraped_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        except Exception:
            logger.exception("Error parsing a Snapdeal product card")
            continue

    logger.info("Returning %d results from Snapdeal", len(results))
    return results


@app.get("/health")
async def health():
    return {"status": "healthy", "platform": PLATFORM, "mode": "live"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
