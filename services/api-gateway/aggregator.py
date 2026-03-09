from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Tuple

import httpx

from config import (
    CACHE_TTL,
    SCRAPER_AMAZON_URL,
    SCRAPER_EBAY_URL,
    SCRAPER_FLIPKART_URL,
    SCRAPER_SNAPDEAL_URL,
)
from models import PriceResult, SearchResponse


logger = logging.getLogger(__name__)

_CACHE: Dict[str, Tuple[float, SearchResponse]] = {}


async def _fetch_scraper(client: httpx.AsyncClient, base_url: str, query: str) -> List[PriceResult]:
    try:
        response = await client.get(
            f"{base_url}/search",
            params={"q": query},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        results_data = data.get("results", [])

        results: List[PriceResult] = []
        for item in results_data:
            try:
                results.append(PriceResult(**item))
            except Exception as exc:
                logger.warning("Failed to parse result from %s: %s", base_url, exc)
        return results
    except Exception as exc:
        logger.warning("Error calling scraper %s: %s", base_url, exc)
        return []


async def aggregate(query: str) -> Tuple[SearchResponse, List[str]]:
    now = time.time()
    cached = _CACHE.get(query)
    if cached is not None:
        timestamp, response = cached
        if now - timestamp < CACHE_TTL:
            logger.info("Cache hit for query=%r", query)
            return response, ["cache"]

    logger.info("Cache miss for query=%r, fetching from scrapers", query)

    scraper_urls = {
        "amazon": SCRAPER_AMAZON_URL,
        "flipkart": SCRAPER_FLIPKART_URL,
        "ebay": SCRAPER_EBAY_URL,
        "snapdeal": SCRAPER_SNAPDEAL_URL,
    }

    start_time = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_scraper(client, url, query) for url in scraper_urls.values()
        ]
        results_or_errors: List[Any] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

    combined_results: List[PriceResult] = []
    responding_scrapers: List[str] = []

    for platform, result in zip(scraper_urls.keys(), results_or_errors):
        if isinstance(result, Exception):
            logger.warning("Scraper %s failed with exception: %s", platform, result)
            continue

        if result:
            combined_results.extend(result)
            responding_scrapers.append(platform)

    best_price = min(combined_results, key=lambda r: r.price) if combined_results else None
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    response = SearchResponse(
        query=query,
        results=combined_results,
        best_price=best_price,
        response_time_ms=elapsed_ms,
    )

    _CACHE[query] = (now, response)

    return response, responding_scrapers

