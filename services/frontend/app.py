"""
PriceRadar v2 — Frontend (Flask)
==================================
Server-side rendered web UI that proxies search requests to the API Gateway.
All API calls go through the Flask backend to avoid CORS and hide infra.
"""

from __future__ import annotations

import logging
import os

import requests
from flask import Flask, jsonify, render_template, request

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger("priceradar.frontend")

app = Flask(__name__)

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")


@app.route("/")
def index():
    """Render the main search page."""
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    """
    Proxy search requests to the API Gateway.
    Passes through query params: q, sort, platform, page, limit.
    """
    params = {
        "q": request.args.get("q", ""),
        "sort": request.args.get("sort", "relevance"),
        "platform": request.args.get("platform", ""),
        "page": request.args.get("page", "1"),
        "limit": request.args.get("limit", "20"),
    }
    # Remove empty params
    params = {k: v for k, v in params.items() if v}

    try:
        resp = requests.get(
            f"{GATEWAY_URL}/search",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        return jsonify(resp.json())
    except requests.Timeout:
        logger.error("Gateway timeout for query: %s", params.get("q"))
        return jsonify({"error": "Search timed out. Please try again.", "results": [], "scraper_errors": []}), 504
    except requests.ConnectionError:
        logger.error("Cannot connect to API Gateway at %s", GATEWAY_URL)
        return jsonify({"error": "Service temporarily unavailable.", "results": [], "scraper_errors": []}), 503
    except Exception as exc:
        logger.exception("Unexpected error proxying search")
        return jsonify({"error": str(exc), "results": [], "scraper_errors": []}), 500


@app.route("/api/platforms")
def api_platforms():
    """Proxy platform health status from the API Gateway."""
    try:
        resp = requests.get(f"{GATEWAY_URL}/platforms", timeout=5)
        resp.raise_for_status()
        return jsonify(resp.json())
    except Exception:
        return jsonify({"platforms": []}), 503


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "frontend"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
