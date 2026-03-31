const searchInput = document.getElementById("search-input");
const searchButton = document.getElementById("search-button");
const summaryBar = document.getElementById("summary-bar");
const summaryCount = document.getElementById("summary-count");
const summaryBest = document.getElementById("summary-best");
const summaryTime = document.getElementById("summary-time");
const errorState = document.getElementById("error-state");
const errorMessage = document.getElementById("error-message");
const skeletonGrid = document.getElementById("skeleton-grid");
const resultsGrid = document.getElementById("results-grid");

function clearResults() {
  resultsGrid.innerHTML = "";
}

function showSkeletons() {
  skeletonGrid.classList.remove("hidden");
  resultsGrid.classList.add("hidden");
  errorState.classList.add("hidden");
  summaryBar.classList.add("hidden");

  skeletonGrid.innerHTML = "";
  const count = 8;
  for (let i = 0; i < count; i++) {
    const card = document.createElement("div");
    card.className = "skeleton-card";
    const line1 = document.createElement("div");
    line1.className = "skeleton-line short";
    const line2 = document.createElement("div");
    line2.className = "skeleton-line long";
    const line3 = document.createElement("div");
    line3.className = "skeleton-line medium";
    card.appendChild(line1);
    card.appendChild(line2);
    card.appendChild(line3);
    skeletonGrid.appendChild(card);
  }
}

function hideSkeletons() {
  skeletonGrid.classList.add("hidden");
}

function formatCurrency(price) {
  return `₹${price.toLocaleString("en-IN", {
    maximumFractionDigits: 2,
  })}`;
}

function platformClass(platform) {
  const name = platform.toLowerCase();
  if (name === "amazon") return "pill-platform-amazon";
  if (name === "flipkart") return "pill-platform-flipkart";
  if (name === "ebay") return "pill-platform-ebay";
  if (name === "snapdeal") return "pill-platform-snapdeal";
  return "";
}

function renderResults(payload) {
  const { query, results, best_price, response_time_ms } = payload;

  clearResults();
  hideSkeletons();

  if (!results || results.length === 0) {
    errorState.classList.remove("hidden");
    errorMessage.textContent =
      `No results found for “${query}”. Try a different product name.`;
    summaryBar.classList.add("hidden");
    resultsGrid.classList.add("hidden");
    return;
  }

  errorState.classList.add("hidden");
  resultsGrid.classList.remove("hidden");

  const platforms = new Set(results.map((r) => r.platform));
  summaryCount.textContent = `${results.length} result${
    results.length !== 1 ? "s" : ""
  } across ${platforms.size} platform${platforms.size !== 1 ? "s" : ""}`;

  if (best_price) {
    summaryBest.textContent = `Best: ${formatCurrency(
      best_price.price
    )} on ${best_price.platform}`;
  } else {
    summaryBest.textContent = "Best: N/A";
  }

  summaryTime.textContent = `Responded in ${response_time_ms.toFixed(1)}ms`;
  summaryBar.classList.remove("hidden");

  let bestKey = null;
  if (best_price) {
    bestKey = `${best_price.platform}__${best_price.product_name}__${best_price.price}`;
  }

  results.forEach((item) => {
    const key = `${item.platform}__${item.product_name}__${item.price}`;
    const isBest = bestKey && key === bestKey;

    const card = document.createElement("div");
    card.className = "card";
    if (isBest) {
      card.classList.add("best-price");
    }

    const header = document.createElement("div");
    header.className = "card-header";

    const badges = document.createElement("div");
    badges.className = "card-badges";

    const platformPill = document.createElement("span");
    platformPill.className = `pill ${platformClass(item.platform)}`;
    platformPill.textContent = item.platform;
    badges.appendChild(platformPill);

    const sourcePill = document.createElement("span");
    sourcePill.className =
      "pill " + (item.source === "live" ? "pill-source-live" : "pill-source-dataset");
    sourcePill.textContent = item.source === "live" ? "LIVE" : "DATASET";
    badges.appendChild(sourcePill);

    header.appendChild(badges);

    if (isBest) {
      const bestBadge = document.createElement("div");
      bestBadge.className = "badge-best";
      bestBadge.textContent = "BEST PRICE 🏆";
      header.appendChild(bestBadge);
    }

    const title = document.createElement("div");
    title.className = "card-title";
    title.textContent = item.product_name;

    const priceRow = document.createElement("div");
    priceRow.className = "card-price-row";

    const price = document.createElement("div");
    price.className = "card-price";
    price.textContent = formatCurrency(item.price);

    const meta = document.createElement("div");
    meta.className = "card-meta";
    meta.textContent =
      item.source === "live"
        ? "Live scraped price"
        : "From curated dataset";

    priceRow.appendChild(price);
    priceRow.appendChild(meta);

    card.appendChild(header);
    card.appendChild(title);
    card.appendChild(priceRow);

    if (item.url) {
      const link = document.createElement("a");
      link.className = "card-link";
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `View on ${item.platform}`;
      card.appendChild(link);
    }

    resultsGrid.appendChild(card);
  });
}

async function performSearch() {
  const query = (searchInput.value || "").trim();
  if (!query) {
    errorState.classList.remove("hidden");
    errorMessage.textContent = "Please enter a product name to search.";
    summaryBar.classList.add("hidden");
    resultsGrid.classList.add("hidden");
    return;
  }

  showSkeletons();

  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed with status ${response.status}`);
    }
    const payload = await response.json();
    renderResults(payload);
  } catch (err) {
    hideSkeletons();
    clearResults();
    errorState.classList.remove("hidden");
    errorMessage.textContent =
      "Something went wrong while fetching prices. Please try again.";
    summaryBar.classList.add("hidden");
    resultsGrid.classList.add("hidden");
    // eslint-disable-next-line no-console
    console.error(err);
  }
}

searchButton.addEventListener("click", () => {
  performSearch();
});

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    performSearch();
  }
});

