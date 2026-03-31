"""
PriceRadar v2 — Myntra Scraper Microservice
=============================================
Live HTTP scraper for myntra.com search results.

EDUCATIONAL / ACADEMIC USE ONLY
--------------------------------
Scraping approach
-----------------
Myntra embeds product data in window.__myx JSON on the search page.
Path: __myx.searchData.results.products

Fallback: HTML card parsing.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

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
logger = logging.getLogger("priceradar.scraper.myntra")

app = FastAPI(title="PriceRadar — Myntra Scraper", version="2.1.0")

BASE_URL = "https://www.myntra.com"
PLATFORM = "Myntra"
PLATFORM_LOGO = "👗"


def _extract_json_object(html: str, marker: str) -> dict | None:
    """Extract a balanced JSON object starting after marker."""
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find('{', idx)
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(html[start:], start):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _parse_myx_products(html: str) -> list[ProductResult]:
    """Parse products from window.__myx embedded JSON."""
    results: list[ProductResult] = []

    data = _extract_json_object(html, "window.__myx =")
    if not data:
        logger.warning("window.__myx not found in Myntra response")
        return results

    products = (
        data
        .get("searchData", {})
        .get("results", {})
        .get("products", [])
    )
    logger.info("Found %d products in Myntra __myx JSON", len(products))

    for item in products[:20]:
        try:
            title = item.get("productName") or item.get("product", "")
            if not title:
                continue

            price = item.get("price") or item.get("mrp", 0)
            try:
                price = float(price)
            except (TypeError, ValueError):
                continue
            if price <= 0:
                continue

            landing = item.get("landingPageUrl", "")
            product_id = item.get("productId", "")
            if landing:
                url = f"{BASE_URL}/{landing}"
            elif product_id:
                url = f"{BASE_URL}/product/{product_id}"
            else:
                url = BASE_URL

            image_url = item.get("searchImage")

            rating = None
            r_val = item.get("rating")
            if r_val is not None:
                try:
                    rating = float(r_val)
                    if rating <= 0 or rating > 5:
                        rating = None
                except (TypeError, ValueError):
                    pass

            review_count = None
            rc = item.get("ratingCount")
            if rc is not None:
                try:
                    review_count = int(rc)
                except (TypeError, ValueError):
                    pass

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
            logger.exception("Error parsing a Myntra product")
            continue

    return results


@app.get("/search", response_model=list[ProductResult])
async def search(q: str = Query(..., min_length=1)):
    logger.info("Searching Myntra for: %s", q)

    await polite_delay()

    search_url = f"{BASE_URL}/{q.replace(' ', '-')}"
    headers = get_default_headers(referer=BASE_URL)

    async with build_client() as client:
        resp = await fetch_with_retry(client, search_url, headers=headers)

    if resp is None:
        logger.warning("Failed to fetch Myntra results for '%s'", q)
        return JSONResponse(content=[], status_code=200)

    results = _parse_myx_products(resp.text)
    logger.info("Returning %d results from Myntra", len(results))
    return results


@app.get("/health")
async def health():
    return {"status": "healthy", "platform": PLATFORM, "mode": "live"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
