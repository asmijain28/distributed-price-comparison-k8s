FROM python:3.12-slim

LABEL maintainer="PriceRadar Team" \
      service="frontend"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    GATEWAY_URL=http://api-gateway:8000

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')"

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:3000", "--workers", "2", "--timeout", "30"]
