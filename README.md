## PriceRadar – Distributed Price Comparison System

PriceRadar is a distributed, microservice-based price comparison platform that fans out search queries to multiple e‑commerce scrapers (Amazon, Flipkart, eBay, Snapdeal), aggregates results through an API gateway, and serves a modern dark UI frontend.

All services are containerized with Docker and can be orchestrated either via `docker-compose` or Kubernetes, with CI/CD powered by GitHub Actions.

### Architecture

```text
          +-----------------------------+
          |         User Browser        |
          +--------------+--------------+
                         |
                         v
             [ Frontend (Flask:3000) ]
                         |
                         v
        [ API Gateway (FastAPI:8000, fan-out/fan-in) ]
                         |
     +-------------------+---------------------------+
     |                   |                           |
     v                   v                           v
[Scraper Amazon:8001] [Scraper Flipkart:8002] [Scraper eBay:8003 (LIVE)]

                        v
               [Scraper Snapdeal:8004 (LIVE)]
```

### Badges

![Python](https://img.shields.io/badge/python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)
![Kubernetes](https://img.shields.io/badge/Kubernetes-manifests-326CE5?logo=kubernetes)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI%2FCD-2088FF?logo=githubactions)

### Platforms

| Platform | Mode    | Currency      | Notes                     |
|----------|---------|---------------|---------------------------|
| Amazon   | Dataset | INR           | Static curated CSV        |
| Flipkart | Dataset | INR           | Static curated CSV        |
| eBay     | Live    | USD → INR     | Live HTML scrape, 83.5 FX |
| Snapdeal | Live    | INR           | Live HTML scrape          |

### Quick Start (Docker Compose)

```bash
docker-compose up --build
```

Then open `http://localhost:3000` in your browser and search for products such as `iPhone 15`, `PS5`, `MacBook Air`, etc.

### Kubernetes Deployment

Apply all manifests from the `k8s/` directory:

```bash
kubectl apply -f k8s/
```

Once deployed, the `frontend-svc` is of type `LoadBalancer` and exposes port 80 to your cluster’s external load balancer.

### Scaling Demo

Demonstrate horizontal scaling of stateless scraper services:

```bash
kubectl scale deployment scraper-amazon --replicas=5
kubectl scale deployment scraper-ebay --replicas=3
kubectl get pods -w
```

Observe additional pods coming online and serving traffic without changing any client configuration.

### API Endpoints

**API Gateway (FastAPI, port 8000)**

| Method | Path         | Description                             |
|--------|--------------|-----------------------------------------|
| GET    | `/search`    | Aggregate search across all scrapers    |
| GET    | `/health`    | Gateway health + list of scrapers       |

**Scraper Services (FastAPI)**

Each scraper exposes the same interface with the shared Pydantic schema:

| Service          | Port | Method | Path       | Description                                 |
|------------------|------|--------|------------|---------------------------------------------|
| scraper-amazon   | 8001 | GET    | `/search`  | Fuzzy match on dataset CSV (INR)            |
|                  |      | GET    | `/health`  | Health check                                |
| scraper-flipkart | 8002 | GET    | `/search`  | Fuzzy match on dataset CSV (INR)            |
|                  |      | GET    | `/health`  | Health check                                |
| scraper-ebay     | 8003 | GET    | `/search`  | Live HTML scraping of eBay (USD→INR)        |
|                  |      | GET    | `/health`  | Health + `mode="live"`                      |
| scraper-snapdeal | 8004 | GET    | `/search`  | Live HTML scraping of Snapdeal (INR)        |
|                  |      | GET    | `/health`  | Health + `mode="live"`                      |

**Frontend (Flask, port 3000)**

| Method | Path          | Description                                  |
|--------|---------------|----------------------------------------------|
| GET    | `/`           | Dark modern UI for entering search queries   |
| GET    | `/api/search` | Server-side proxy to API gateway `/search`   |

### Environment Variables

| Variable             | Default                       | Used By        | Description                                 |
|----------------------|-------------------------------|----------------|---------------------------------------------|
| `SCRAPER_AMAZON_URL`   | `http://localhost:8001`       | api-gateway    | Base URL for Amazon scraper                 |
| `SCRAPER_FLIPKART_URL` | `http://localhost:8002`       | api-gateway    | Base URL for Flipkart scraper               |
| `SCRAPER_EBAY_URL`     | `http://localhost:8003`       | api-gateway    | Base URL for eBay scraper                   |
| `SCRAPER_SNAPDEAL_URL` | `http://localhost:8004`       | api-gateway    | Base URL for Snapdeal scraper               |
| `CACHE_TTL`            | `300`                         | api-gateway    | In-memory cache TTL in seconds              |
| `GATEWAY_URL`         | `http://localhost:8000`       | frontend       | Base URL for API gateway                    |

In Kubernetes, these are provided via the `price-comparison-config` `ConfigMap` and consumed with `envFrom` or `configMapKeyRef` as appropriate.

### Distributed Systems Concepts Demonstrated

- **Fan-out/Fan-in aggregation**: The API gateway fans out a search request to four independent scrapers using `asyncio.gather(return_exceptions=True)` and then aggregates the results into a single normalized response.
- **Fault isolation**: Any scraper can fail or time out without affecting the overall response; failures are logged and skipped so the gateway always returns the best effort set of results.
- **Horizontal scaling**: Scraper deployments use replicas in Kubernetes, and can be scaled up/down independently to handle traffic spikes for specific platforms.
- **Service discovery via Kubernetes DNS**: Scraper and gateway services discover each other via stable ClusterIP service names (`scraper-amazon-svc`, `gateway-svc`, etc.).
- **Health probes**: All services expose `/health` endpoints used by Kubernetes liveness and readiness probes for robust self-healing.
- **In-memory caching**: The gateway caches search responses per query for a configurable TTL, reducing latency and external load for repeated queries.

### Development Notes

- All services are self-contained with their own `requirements.txt` and `Dockerfile`.
- Dataset-based scrapers load CSVs once at startup and serve from memory.
- Live scrapers (eBay, Snapdeal) wrap all scraping logic in defensive `try/except` blocks, returning an empty result set on any error rather than propagating exceptions.
- The frontend never calls scrapers or the gateway directly from the browser; instead, it proxies via Flask `/api/search` to avoid CORS and to keep infrastructure details server-side.
