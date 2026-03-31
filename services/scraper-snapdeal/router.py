from __future__ import annotations

import logging
import time
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Query
from models import PriceResult, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter()

SNAPDEAL_SEARCH_URL = "https://www.snapdeal.com/search"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_inr_price(text: str) -> float:
    """
    Parse Snapdeal price string like 'Rs. 59,999' or '₹59,999' into float INR.
    """
    if not text:
        raise ValueError("Empty price string")

    cleaned = (
        text.replace("Rs.", "")
        .replace("Rs", "")
        .replace("₹", "")
        .replace(",", "")
        .strip()
    )
    if not cleaned:
        raise ValueError(f"Unable to parse price from: {text!r}")
    return float(cleaned)


def _absolute_url(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return f"https://www.snapdeal.com{href}"
    return f"https://www.snapdeal.com/{href.lstrip('/')}"


def _scrape_snapdeal(query: str) -> List[PriceResult]:
    """
    Perform the HTTP request and parse HTML to extract up to 5 results.
    All scraping logic is wrapped in try/except and returns [] on failure.
    """
    try:
        response = requests.get(
            SNAPDEAL_SEARCH_URL,
            params={"keyword": query, "sort": "rlvncy"},
            headers=REQUEST_HEADERS,
            timeout=10,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select("div.product-tuple-listing")

        results: List[PriceResult] = []
        for item in items:
            title_el = item.select_one(".product-title")
            price_el = item.select_one(".product-price")

            if not title_el or not price_el:
                continue

            title = title_el.get_text(strip=True)
            raw_price = price_el.get_text(strip=True)

            try:
                price_inr = _parse_inr_price(raw_price)
            except Exception as exc:  # pragma: no cover - HTML variability
                logger.debug("Failed to parse Snapdeal price %r: %s", raw_price, exc)
                continue

            link_el = item.select_one("a.dp-widget-link") or item.find("a")
            url = _absolute_url(link_el.get("href")) if link_el else None

            results.append(
                PriceResult(
                    platform="snapdeal",
                    product_name=title,
                    price=round(price_inr, 2),
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
        logger.error("Error scraping Snapdeal for query %r: %s", query, exc)
        return []


@router.get("/search", response_model=SearchResponse)
async def search_snapdeal(q: str = Query(..., min_length=1, description="Search query")) -> SearchResponse:
    """
    Live search on Snapdeal, returning up to 5 results in INR.
    """
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    start_time = time.perf_counter()

    results = _scrape_snapdeal(query)
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
    return {"status": "ok", "service": "scraper-snapdeal", "mode": "live"}

