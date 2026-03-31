# 📡 PriceRadar v2 — Live Indian E-Commerce Price Comparison

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)](https://docker.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-manifests-326CE5?logo=kubernetes)](https://kubernetes.io)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI%2FCD-2088FF?logo=githubactions)](https://github.com/features/actions)

**PriceRadar v2** is a distributed, microservice-based price comparison system that **live-scrapes** India's top e-commerce platforms, aggregates results through an API gateway, and serves a modern product comparison UI.

> **v2 improvements over v1:**  
> Removed all CSV/dataset-based mock scrapers. Removed non-Indian platforms (eBay, Snapdeal). Added **6 live Indian platform scrapers**, modernised the frontend (Flash.co-inspired), added sorting/filtering/pagination, HPA autoscaling, and a CI/CD pipeline.

---

## Architecture

```
                        ┌─────────────────────┐
                        │    User Browser      │
                        └──────────┬──────────┘
                                   │
                                   ▼
                      ┌────────────────────────┐
                      │  Frontend (Flask:3000)  │
                      │  Jinja2 + Modern CSS/JS │
                      └────────────┬───────────┘
                                   │  /api/search proxy
                                   ▼
               ┌───────────────────────────────────────┐
               │      API Gateway (FastAPI:8000)        │
               │  Fan-out · Cache · Sort · Paginate     │
               └───┬───┬───┬───┬───┬───┬───────────────┘
                   │   │   │   │   │   │
          ┌────────┘   │   │   │   │   └────────┐
          ▼            ▼   ▼   ▼   ▼            ▼
     ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
     │ Amazon  │ │Flipkart │ │ Myntra  │ │ Meesho  │
     │  :8001  │ │  :8002  │ │  :8003  │ │  :8004  │
     └─────────┘ └─────────┘ └─────────┘ └─────────┘
                         ┌─────────┐ ┌─────────┐
                         │  Nykaa  │ │  Croma  │
                         │  :8005  │ │  :8006  │
                         └─────────┘ └─────────┘
```

All scraper services are independently deployable FastAPI containers. The gateway fans out search queries to all (or filtered) scrapers using `asyncio.gather(return_exceptions=True)` and merges the results.

---

## Platforms Covered

| Platform | Port | Category Focus | Scraping Approach |
|----------|------|----------------|-------------------|
| **Amazon India** | 8001 | All categories | HTML parsing of `amazon.in/s?k=` search results (`.s-result-item` cards) |
| **Flipkart** | 8002 | All categories | JSON extraction from embedded `<script>` tags, HTML fallback |
| **Myntra** | 8003 | Fashion, apparel | Gateway JSON API (`/gateway/v2/search/`), HTML fallback |
| **Meesho** | 8004 | Value fashion, home | `__NEXT_DATA__` JSON extraction, HTML card fallback |
| **Nykaa** | 8005 | Beauty, wellness | `__PRELOADED_STATE__` JSON extraction, HTML fallback |
| **Croma** | 8006 | Electronics | `__NEXT_DATA__` JSON extraction, HTML card fallback |

All prices are in **₹ INR**. No currency conversion needed.

---

## Quick Start

### Docker Compose (recommended for local dev)

```bash
# Clone and enter the project
git clone https://github.com/<your-org>/priceradar-v2.git
cd priceradar-v2

# Build and start all services
docker-compose up --build

# Or use the Makefile
make up
```

Open **http://localhost:3000** and search for products.

### Kubernetes

```bash
# Apply all manifests
kubectl apply -f k8s/

# Check status
kubectl get pods,svc,hpa -l app=priceradar

# The frontend is exposed as a LoadBalancer on port 80
kubectl get svc frontend-svc
```

### Scaling Demo

```bash
# Scale Amazon scraper to 5 replicas
kubectl scale deployment scraper-amazon --replicas=5

# Scale API gateway (or let HPA auto-scale at 70% CPU)
kubectl scale deployment api-gateway --replicas=4

# Watch pods come up
kubectl get pods -w -l app=priceradar
```

---

## API Reference

### Gateway — `GET /search`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | *required* | Search query |
| `sort` | string | `relevance` | `relevance`, `price_asc`, `price_desc`, `rating` |
| `platform` | string | *(all)* | Comma-separated filter: `amazon,flipkart` |
| `page` | int | `1` | Page number |
| `limit` | int | `20` | Results per page (max 100) |

**Response:**

```json
{
  "query": "iPhone 16",
  "total_results": 42,
  "page": 1,
  "limit": 20,
  "sort": "price_asc",
  "platforms_queried": ["amazon", "flipkart", "croma"],
  "results": [ ... ],
  "scraper_errors": [
    {"source": "Myntra", "error_type": "timeout", "message": "..."}
  ],
  "cached": false
}
```

### Gateway — `GET /platforms`

Returns health status and response times for all registered scrapers.

### All Services — `GET /health`

Returns `{"status": "healthy", ...}`.

---

## Environment Variables

| Variable | Default | Used By | Description |
|----------|---------|---------|-------------|
| `SCRAPER_AMAZON_URL` | `http://localhost:8001` | Gateway | Amazon scraper base URL |
| `SCRAPER_FLIPKART_URL` | `http://localhost:8002` | Gateway | Flipkart scraper base URL |
| `SCRAPER_MYNTRA_URL` | `http://localhost:8003` | Gateway | Myntra scraper base URL |
| `SCRAPER_MEESHO_URL` | `http://localhost:8004` | Gateway | Meesho scraper base URL |
| `SCRAPER_NYKAA_URL` | `http://localhost:8005` | Gateway | Nykaa scraper base URL |
| `SCRAPER_CROMA_URL` | `http://localhost:8006` | Gateway | Croma scraper base URL |
| `CACHE_TTL` | `300` | Gateway | In-memory cache TTL (seconds) |
| `GATEWAY_TIMEOUT_SECONDS` | `10` | Gateway | Max wait for a scraper response |
| `SCRAPE_DELAY_MS` | `500` | Scrapers | Polite delay between requests (ms) |
| `SCRAPE_TIMEOUT_SECONDS` | `8` | Scrapers | Per-request timeout |
| `GATEWAY_URL` | `http://localhost:8000` | Frontend | Gateway URL for Flask proxy |

---

## Project Structure

```
priceradar-v2/
├── services/
│   ├── common/                    # Shared code (mounted into scraper containers)
│   │   ├── schemas.py             # ProductResult Pydantic model
│   │   └── scraper_utils.py       # UA rotation, retry, throttling
│   ├── scraper-amazon/            # Amazon India scraper
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── scraper-flipkart/          # Flipkart scraper
│   ├── scraper-myntra/            # Myntra scraper
│   ├── scraper-meesho/            # Meesho scraper
│   ├── scraper-nykaa/             # Nykaa scraper
│   ├── scraper-croma/             # Croma scraper
│   ├── api-gateway/               # Central aggregation gateway
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── frontend/                  # Flask web UI
│       ├── app.py
│       ├── templates/index.html
│       ├── static/css/style.css
│       ├── static/js/app.js
│       ├── requirements.txt
│       └── Dockerfile
├── k8s/                           # Kubernetes manifests
│   ├── 00-configmap.yaml
│   ├── 01-scraper-amazon.yaml
│   ├── 02-scraper-flipkart.yaml
│   ├── 03-scraper-myntra.yaml
│   ├── 04-scraper-meesho.yaml
│   ├── 05-scraper-nykaa.yaml
│   ├── 06-scraper-croma.yaml
│   ├── 07-api-gateway.yaml
│   ├── 08-frontend.yaml
│   └── 09-hpa.yaml
├── .github/workflows/ci.yml      # CI/CD pipeline
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## Anti-Bot & Resilience Strategy

Live scraping Indian e-commerce platforms is challenging due to active bot protection.

### What PriceRadar does:

1. **Rotating User-Agents** — Pool of 10 real Chrome/Safari/Firefox UA strings, rotated per request
2. **Browser-like headers** — `Accept-Language: en-IN`, `Sec-Fetch-*`, `Referer` headers mimic real browser navigation
3. **Request throttling** — Configurable `SCRAPE_DELAY_MS` (default 500ms) between requests
4. **Retry on transient errors** — HTTP 429/503 triggers one retry after `SCRAPE_DELAY_MS × 2`
5. **Per-request timeout** — `SCRAPE_TIMEOUT_SECONDS` (default 8s) prevents hanging
6. **Gateway-level timeout** — `GATEWAY_TIMEOUT_SECONDS` (default 10s) caps total wait
7. **Graceful degradation** — If a scraper errors/times out, the gateway returns results from other scrapers with structured error reporting
8. **HTTP/2 support** — `httpx` with HTTP/2 for better connection reuse

### Known Limitations

- **Amazon India** aggressively detects automated requests. May return CAPTCHAs or empty pages after repeated queries. In production, use the [PA-API 5.0](https://webservices.amazon.com/paapi5/documentation/).
- **Flipkart** frequently rotates CSS class names. Selectors may break without notice.
- **Myntra's gateway API** may require session tokens. Falls back to HTML parsing.
- **Meesho** is heavily mobile-first and may serve different HTML to desktop UAs.

### Production Recommendations

For production use, consider licensed scraping APIs:
- [ScraperAPI](https://www.scraperapi.com/) — handles proxies and CAPTCHAs
- [Bright Data](https://brightdata.com/) — web scraping infrastructure
- [Oxylabs](https://oxylabs.io/) — e-commerce scraping API
- Official affiliate/partner APIs where available

---

## Adding a New Scraper Platform

1. Create `services/scraper-<name>/main.py` following the existing pattern:
   - Import `ProductResult` from `common/schemas.py`
   - Import helpers from `common/scraper_utils.py`
   - Implement `GET /search?q=<query>` returning `list[ProductResult]`
   - Implement `GET /health`
2. Add `requirements.txt` and `Dockerfile` (copy from an existing scraper, change the port)
3. Register the scraper in `services/api-gateway/main.py` → `SCRAPERS` dict
4. Add the service to `docker-compose.yml`
5. Create a K8s manifest in `k8s/`
6. Add a platform chip to `services/frontend/templates/index.html`

---

## Distributed Systems Concepts Demonstrated

- **Fan-out / Fan-in aggregation** — Gateway parallelises requests across 6 scraper services
- **Fault isolation** — Any scraper can fail without affecting the overall response
- **Horizontal scaling** — Each scraper scales independently via K8s replicas
- **Service discovery** — Kubernetes DNS for inter-service communication
- **Auto-scaling** — HPA scales the gateway based on CPU utilisation
- **Health probes** — Liveness + readiness probes for self-healing
- **In-memory caching** — TTL cache at the gateway reduces repeated scraping
- **Graceful degradation** — Structured error reporting alongside partial results

---

## Acknowledgements

- UI design inspired by [flash.co](https://flash.co/home) — an AI-powered Indian product research platform
- Built as an academic project for **Manipal University Jaipur, B.Tech CS (Data Science)**

---

## Disclaimer

This project is built for **educational and academic purposes only**. The scrapers are designed to demonstrate distributed systems concepts. In production:

- Comply with each platform's Terms of Service
- Use official APIs or licensed data feeds where available
- Respect `robots.txt` and rate limits
- Consider the legal implications of web scraping in your jurisdiction
