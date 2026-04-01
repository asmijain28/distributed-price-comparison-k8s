"""
PriceRadar v2 — API Gateway
=============================
Central aggregation service that fans out search queries to all registered
scraper microservices, merges results, and returns a unified, sorted,
paginated response.

Features
--------
- Concurrent fan-out via ``asyncio.gather(return_exceptions=True)``
- Per-query TTL caching (300 s default)
- Sorting: price_asc, price_desc, rating (desc), relevance (default)
- Platform filtering: ``?platform=amazon,flipkart``
- Pagination: ``?page=1&limit=20``
- ``/platforms`` endpoint returning health status of every scraper
- Structured ``scraper_errors`` alongside results on partial failure
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx
from cachetools import TTLCache
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("priceradar.gateway")

# ── FastAPI app ─────────────────────────────────────────────────────────
app = FastAPI(
    title="PriceRadar v2 — API Gateway",
    version="2.0.0",
    description="Aggregates live search results from Indian e-commerce scrapers.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Scraper registry ────────────────────────────────────────────────────
# Each entry maps a platform key to its base URL (configurable via env).

SCRAPERS: dict[str, dict[str, str]] = {
    "amazon": {
        "name": "Amazon",
        "url": os.getenv("SCRAPER_AMAZON_URL", "http://localhost:8001"),
        "logo": "🛒",
    },
    "flipkart": {
        "name": "Flipkart",
        "url": os.getenv("SCRAPER_FLIPKART_URL", "http://localhost:8002"),
        "logo": "🏷️",
    },
    "myntra": {
        "name": "Myntra",
        "url": os.getenv("SCRAPER_MYNTRA_URL", "http://localhost:8003"),
        "logo": "👗",
    },
    "snapdeal": {
        "name": "Snapdeal",
        "url": os.getenv("SCRAPER_SNAPDEAL_URL", "http://localhost:8004"),
        "logo": "🔖",
    },
}

# ── Configuration ───────────────────────────────────────────────────────
CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))
GATEWAY_TIMEOUT: float = float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "10"))

# In-memory TTL cache keyed on (query, sort, platform_filter)
# maxsize=256 keeps memory bounded
_cache: TTLCache = TTLCache(maxsize=256, ttl=CACHE_TTL)

VALID_SORTS = {"relevance", "price_asc", "price_desc", "rating"}


# ── Helpers ─────────────────────────────────────────────────────────────

async def _call_scraper(
    client: httpx.AsyncClient,
    key: str,
    info: dict[str, str],
    query: str,
) -> tuple[str, list[dict[str, Any]], Optional[dict[str, str]]]:
    """
    Call a single scraper's /search endpoint.

    Returns (platform_key, results_list, error_or_None).
    On failure, returns an empty list and a structured error dict.
    """
    url = f"{info['url']}/search"
    try:
        resp = await client.get(url, params={"q": query}, timeout=GATEWAY_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return (key, data, None)
        return (key, [], None)
    except httpx.TimeoutException:
        logger.warning("Timeout calling %s scraper", info["name"])
        return (
    key,
    [],
    {
        "source": info["name"],
        "error_type": "timeout",
        "message": f"{info['name']} scraper timed out after {GATEWAY_TIMEOUT}s",
    },
)
    except httpx.HTTPStatusError as exc:
        logger.warning("HTTP %d from %s scraper", exc.response.status_code, info["name"])
        return (
    key,
    [],
    {
        "source": info["name"],
        "error_type": "http_error",
        "message": f"HTTP {exc.response.status_code}",
    },
)
    except Exception as exc:
        logger.exception("Error calling %s scraper", info["name"])
        return (key, [], {"source": info["name"], "error_type": "connection_error", "message": str(exc)})


def _sort_results(results: list[dict], sort: str) -> list[dict]:
    """Sort the merged results list."""
    if sort == "price_asc":
        return sorted(results, key=lambda r: r.get("price", float("inf")))
    elif sort == "price_desc":
        return sorted(results, key=lambda r: r.get("price", 0), reverse=True)
    elif sort == "rating":
        return sorted(
            results,
            key=lambda r: r.get("rating") or 0,
            reverse=True,
        )
    # "relevance" — return in scraper order (Amazon first, etc.)
    return results


# ── Endpoints ───────────────────────────────────────────────────────────

@app.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    sort: str = Query("relevance", description="Sort order: relevance, price_asc, price_desc, rating"),
    platform: Optional[str] = Query(None, description="Comma-separated platform filter, e.g. 'amazon,flipkart'"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
):
    """
    Fan-out search to all (or filtered) scraper services, merge, sort, paginate.
    """
    if sort not in VALID_SORTS:
        sort = "relevance"

    # Determine which scrapers to query
    platform_filter: Optional[set[str]] = None
    if platform:
        platform_filter = {p.strip().lower() for p in platform.split(",")}

    active_scrapers = {
        k: v for k, v in SCRAPERS.items()
        if platform_filter is None or k in platform_filter
    }

    # Check cache
    cache_key = (q.lower().strip(), sort, frozenset(active_scrapers.keys()))
    cached = _cache.get(cache_key)
    if cached is not None:
        logger.info("Cache HIT for query='%s'", q)
        all_results, scraper_errors = cached
    else:
        logger.info("Cache MISS — fanning out to %d scrapers for query='%s'", len(active_scrapers), q)

        async with httpx.AsyncClient() as client:
            tasks = [
                _call_scraper(client, key, info, q)
                for key, info in active_scrapers.items()
            ]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        all_results: list[dict[str, Any]] = []
        scraper_errors: list[dict[str, str]] = []

        for outcome in outcomes:
            if isinstance(outcome, Exception):
                logger.exception("Unexpected exception in gather: %s", outcome)
                scraper_errors.append({
                    "source": "unknown",
                    "error_type": "internal",
                    "message": str(outcome),
                })
                continue
            _key, results, error = outcome
            all_results.extend(results)
            if error:
                scraper_errors.append(error)

        # Cache the raw (unsorted) results + errors
        _cache[cache_key] = (all_results, scraper_errors)

    # Sort
    sorted_results = _sort_results(all_results, sort)

    # Find the global best price index and tag it
    if sorted_results:
        best_idx = min(
            range(len(sorted_results)),
            key=lambda i: sorted_results[i].get("price") or float("inf"),
        )
        # Move it to position 0
        if best_idx != 0:
            best_item = sorted_results.pop(best_idx)
            sorted_results.insert(0, best_item)
        # Tag only the first item as global best
        sorted_results[0] = {**sorted_results[0], "global_best": True}

    # Paginate
    total = len(sorted_results)
    start = (page - 1) * limit
    end = start + limit
    page_results = sorted_results[start:end]

    return {
        "query": q,
        "total_results": total,
        "page": page,
        "limit": limit,
        "sort": sort,
        "platforms_queried": list(active_scrapers.keys()),
        "results": page_results,
        "scraper_errors": scraper_errors,
        "cached": _cache.get(cache_key) is not None,
    }


@app.get("/platforms")
async def platforms():
    """List all registered scrapers and their current health status."""
    statuses = []

    async with httpx.AsyncClient(timeout=3.0) as client:
        for key, info in SCRAPERS.items():
            t0 = time.monotonic()
            try:
                resp = await client.get(f"{info['url']}/health")
                resp.raise_for_status()
                ms = (time.monotonic() - t0) * 1000
                statuses.append({
                    "name": info["name"],
                    "key": key,
                    "url": info["url"],
                    "healthy": True,
                    "mode": "live",
                    "response_time_ms": round(ms, 1),
                })
            except Exception:
                ms = (time.monotonic() - t0) * 1000
                statuses.append({
                    "name": info["name"],
                    "key": key,
                    "url": info["url"],
                    "healthy": False,
                    "mode": "live",
                    "response_time_ms": round(ms, 1),
                })

    return {"platforms": statuses}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "api-gateway",
        "scrapers_registered": len(SCRAPERS),
        "cache_size": len(_cache),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
