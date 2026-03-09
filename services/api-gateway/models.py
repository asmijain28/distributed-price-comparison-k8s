from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class PriceResult(BaseModel):
    platform: str = Field(..., description="Name of the e-commerce platform")
    product_name: str = Field(..., description="Human readable product title")
    price: float = Field(..., ge=0, description="Product price in INR")
    currency: str = Field("INR", description="ISO currency code, default INR")
    available: bool = Field(True, description="Whether the item is available")
    source: str = Field(..., description='"dataset" or "live"')
    url: Optional[str] = Field(
        None,
        description="Optional product URL on the source platform",
    )


class SearchResponse(BaseModel):
    query: str = Field(..., description="Original search query")
    results: List[PriceResult] = Field(
        default_factory=list, description="Flat list of price results"
    )
    best_price: Optional[PriceResult] = Field(
        None, description="Best (lowest) price across all platforms"
    )
    response_time_ms: float = Field(
        ..., ge=0, description="End-to-end response time in milliseconds"
    )

