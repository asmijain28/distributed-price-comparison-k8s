from __future__ import annotations

import os

import requests
from flask import Flask, jsonify, render_template, request


app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"detail": "Query must not be empty"}), 400

    gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
    try:
        response = requests.get(
            f"{gateway_url}/search",
            params={"q": query},
            timeout=15,
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as exc:
        return jsonify({"detail": f"Failed to reach API gateway: {exc}"}), 502


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=3000, debug=False)

