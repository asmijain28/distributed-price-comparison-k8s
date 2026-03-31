"""
PriceRadar v2 — Shared Product Schema
======================================
Normalised Pydantic model returned by every scraper microservice.
The API Gateway merges lists of ProductResult from each scraper into
a single sorted, paginated response.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class ProductResult(BaseModel):
    """Canonical product representation across all Indian e-commerce platforms."""

    title: str = Field(..., description="Product title / name")
    price: float = Field(..., ge=0, description="Price in INR")
    currency: str = Field(default="INR", description="Always INR for Indian platforms")
    platform: str = Field(..., description="Source platform name, e.g. 'Amazon', 'Flipkart'")
    platform_logo: str = Field(default="🛒", description="Emoji badge for the platform")
    url: str = Field(..., description="Direct deep-link to the product page")
    image_url: Optional[str] = Field(default=None, description="Product image URL")
    rating: Optional[float] = Field(default=None, ge=0, le=5, description="Rating out of 5")
    review_count: Optional[int] = Field(default=None, ge=0, description="Number of reviews")
    availability: str = Field(default="In Stock", description="Stock status string")
    scraped_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 timestamp of when the result was scraped",
    )


class ScraperError(BaseModel):
    """Structured error returned when a scraper fails."""

    source: str
    error_type: str
    message: str


class SearchResponse(BaseModel):
    """Top-level response envelope from the API Gateway."""

    query: str
    total_results: int
    page: int
    limit: int
    sort: str
    platforms_queried: list[str]
    results: list[ProductResult]
    scraper_errors: list[ScraperError] = Field(default_factory=list)
    cached: bool = False


class PlatformStatus(BaseModel):
    """Health status of a single scraper platform."""

    name: str
    url: str
    healthy: bool
    mode: str = "live"
    response_time_ms: Optional[float] = None
