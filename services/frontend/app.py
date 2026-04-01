"""
PriceRadar v2 — Frontend (Flask)
==================================
Server-side rendered web UI that proxies search requests to the API Gateway.
All API calls go through the Flask backend to avoid CORS and hide infra.
"""

from __future__ import annotations

import base64
import io
import logging
import os

import requests
from flask import Flask, jsonify, render_template, request
from PIL import Image

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


@app.route("/api/image-search", methods=["POST"])
def api_image_search():
    """
    Accept an uploaded image and return a search query string derived from it.
    Uses Google Gemini Vision if GEMINI_API_KEY is set, otherwise falls back
    to a cleaned-up version of the filename.
    """
    file = request.files.get("image")
    if not file:
        return jsonify({"error": "No image provided"}), 400

    gemini_key = os.getenv("GEMINI_API_KEY", "")

    if gemini_key:
        try:
            # Resize to keep payload small, then base64-encode
            img = Image.open(file.stream).convert("RGB")
            img.thumbnail((512, 512))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            b64 = base64.b64encode(buf.getvalue()).decode()

            payload = {
                "contents": [{
                    "parts": [
                        {"text": "Identify the product in this image. Reply with only a short search query (2-5 words) suitable for searching on an e-commerce site like Amazon or Flipkart. No explanation, just the query."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                    ]
                }]
            }
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            query = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            logger.info("Gemini image query: %s", query)
            return jsonify({"query": query})
        except Exception as exc:
            logger.warning("Gemini vision failed, falling back to filename: %s", exc)

    # Fallback: derive query from filename
    import re
    name = file.filename or "product"
    name = re.sub(r"\.[^.]+$", "", name)          # strip extension
    name = re.sub(r"[_\-]+", " ", name)            # underscores/dashes → spaces
    name = re.sub(r"\b(img|image|photo|pic|dsc|screenshot|\d{4,})\b", "", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip()
    query = name if len(name) > 2 else "product"
    return jsonify({"query": query})


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "service": "frontend"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)
