import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from aggregator import aggregate
from models import SearchResponse


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Price Comparison Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=1, description="Search query")) -> SearchResponse:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    response, scrapers = await aggregate(query)

    logger.info(
        "Search completed query=%r count=%d duration_ms=%.2f scrapers=%s",
        response.query,
        len(response.results),
        response.response_time_ms,
        ",".join(scrapers),
    )

    return response


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "api-gateway",
        "scrapers": ["amazon", "flipkart", "ebay", "snapdeal"],
    }


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)