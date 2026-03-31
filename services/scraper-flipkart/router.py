from __future__ import annotations

import asyncio
import random
import time
from typing import List

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from models import PriceResult, SearchResponse

router = APIRouter()

_DATAFRAME: pd.DataFrame | None = None


def _load_dataset() -> pd.DataFrame:
    """
    Load the products CSV once at startup and keep it in memory.
    """
    global _DATAFRAME
    if _DATAFRAME is not None:
        return _DATAFRAME

    try:
        df = pd.read_csv("data/products.csv")
    except Exception as exc:  # pragma: no cover - defensive fallback
        raise RuntimeError(f"Failed to load Flipkart dataset: {exc}") from exc

    required_columns = {"product_name", "platform", "price", "url"}
    missing = required_columns - set(df.columns)
    if missing:
        raise RuntimeError(f"Flipkart dataset missing columns: {missing}")

    _DATAFRAME = df
    return _DATAFRAME


_load_dataset()


@router.get("/search", response_model=SearchResponse)
async def search_products(q: str = Query(..., min_length=1, description="Search query")) -> SearchResponse:
    """
    Perform a fuzzy, case-insensitive search over product_name and return
    all matching rows as PriceResult objects.
    """
    start_time = time.perf_counter()

    await asyncio.sleep(random.uniform(0.05, 0.15))

    df = _load_dataset()
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    mask = df["product_name"].str.contains(query, case=False, na=False)
    matched = df[mask].copy()

    results: List[PriceResult] = []
    for _, row in matched.iterrows():
        results.append(
            PriceResult(
                platform=str(row["platform"]),
                product_name=str(row["product_name"]),
                price=float(row["price"]),
                currency="INR",
                available=True,
                source="dataset",
                url=str(row["url"]) if not pd.isna(row["url"]) else None,
            )
        )

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
    return {"status": "ok", "service": "scraper-flipkart"}

