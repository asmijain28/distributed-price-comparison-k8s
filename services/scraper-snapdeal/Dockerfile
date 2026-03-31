FROM python:3.12-slim

LABEL maintainer="PriceRadar Team" \
      service="scraper-snapdeal"

WORKDIR /app

COPY scraper-snapdeal/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common/ /app/common/
COPY scraper-snapdeal/main.py .

ENV PYTHONUNBUFFERED=1 \
    SCRAPE_DELAY_MS=500 \
    SCRAPE_TIMEOUT_SECONDS=8

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004", "--workers", "2"]
