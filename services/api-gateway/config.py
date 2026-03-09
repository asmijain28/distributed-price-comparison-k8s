from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

SCRAPER_AMAZON_URL: str = os.getenv("SCRAPER_AMAZON_URL", "http://localhost:8001")
SCRAPER_FLIPKART_URL: str = os.getenv("SCRAPER_FLIPKART_URL", "http://localhost:8002")
SCRAPER_EBAY_URL: str = os.getenv("SCRAPER_EBAY_URL", "http://localhost:8003")
SCRAPER_SNAPDEAL_URL: str = os.getenv("SCRAPER_SNAPDEAL_URL", "http://localhost:8004")

CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))

