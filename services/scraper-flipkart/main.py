from __future__ import annotations

from fastapi import FastAPI

from router import router


app = FastAPI(title="Flipkart Scraper Service", version="1.0.0")

app.include_router(router)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)

