from __future__ import annotations

import logging
import time
from typing import List

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Query
from models import PriceResult, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter()

EBAY_SEARCH_URL = "https://www.ebay.com/sch/i.html"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

USD_TO_INR = 83.5


def _parse_price(text: str) -> float:
    """
    Parse an eBay price string like '$799.99', '$799.99 to $899.99'
    into a float value (lower bound of range) in USD.
    """
    if not text:
        raise ValueError("Empty price string")

    cleaned = text.replace(",", "").strip()
    if "to" in cleaned:
        cleaned = cleaned.split("to", 1)[0].strip()

    cleaned = cleaned.replace("$", "").strip()
    if not cleaned:
        raise ValueError(f"Unable to parse price from: {text!r}")

    return float(cleaned)


def _scrape_ebay(query: str) -> List[PriceResult]:
    """
    Perform the HTTP request and parse HTML to extract up to 5 results.
    All scraping logic is wrapped in try/except and returns [] on failure.
    """
    try:
        response = requests.get(
            EBAY_SEARCH_URL,
            params={"_nkw": query, "_sacat": 0},
            headers=REQUEST_HEADERS,
            timeout=10,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select("li.s-item")

        results: List[PriceResult] = []
        for item in items:
            title_el = item.select_one(".s-item__title")
            if not title_el:
                continue

            title_text = title_el.get_text(strip=True)
            if not title_text or title_text == "Shop on eBay" or title_text.startswith("New Listing"):
                continue

            price_el = item.select_one(".s-item__price")
            link_el = item.select_one("a.s-item__link")

            if not price_el or not link_el:
                continue

            try:
                usd_price = _parse_price(price_el.get_text(strip=True))
            except Exception as exc:  # pragma: no cover - HTML variability
                logger.debug("Failed to parse price from %r: %s", price_el.get_text(), exc)
                continue

            inr_price = usd_price * USD_TO_INR
            url = link_el.get("href") or None

            results.append(
                PriceResult(
                    platform="ebay",
                    product_name=title_text,
                    price=round(inr_price, 2),
                    currency="INR",
                    available=True,
                    source="live",
                    url=url,
                )
            )

            if len(results) >= 5:
                break

        return results
    except Exception as exc:  # pragma: no cover - network dependent
        logger.error("Error scraping eBay for query %r: %s", query, exc)
        return []


@router.get("/search", response_model=SearchResponse)
async def search_ebay(q: str = Query(..., min_length=1, description="Search query")) -> SearchResponse:
    """
    Live search on eBay, returning up to 5 results converted to INR.
    """
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    start_time = time.perf_counter()

    results = _scrape_ebay(query)
    best_price = min(results, key=lambda r: r.price) if results else None
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return SearchResponse(
        query=query,
        results=results,
        best_price=best_price,
        response_time_ms=elapsed_ms,
    )


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "scraper-ebay", "mode": "live"}

