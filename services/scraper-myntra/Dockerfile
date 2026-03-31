FROM python:3.12-slim

LABEL maintainer="PriceRadar Team" \
      service="scraper-myntra"

WORKDIR /app

# Install deps first (Docker layer cache)
COPY scraper-myntra/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules (build context = services/)
COPY common/ /app/common/

# Copy service code
COPY scraper-myntra/main.py .

ENV PYTHONUNBUFFERED=1 \
    SCRAPE_DELAY_MS=500 \
    SCRAPE_TIMEOUT_SECONDS=8

EXPOSE 8003

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--workers", "2"]
