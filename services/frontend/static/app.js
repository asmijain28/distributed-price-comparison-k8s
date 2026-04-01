// ── Element references (matching current index.html IDs exactly) ────
const searchInput   = document.getElementById("searchInput");
const searchBtn     = document.getElementById("searchBtn");
const skeletonGrid  = document.getElementById("skeletonGrid");
const productGrid   = document.getElementById("productGrid");
const emptyState    = document.getElementById("emptyState");
const errorState    = document.getElementById("errorState");
const errorTitle    = document.getElementById("errorTitle");
const errorMessage  = document.getElementById("errorMessage");
const controlsBar   = document.getElementById("controlsBar");
const statusBar     = document.getElementById("statusBar");
const resultCount   = document.getElementById("resultCount");
const cacheStatus   = document.getElementById("cacheStatus");
const pagination    = document.getElementById("pagination");
const themeToggle   = document.getElementById("themeToggle");

// ── Image upload elements ────────────────────────────────────────────
const cameraInput   = document.getElementById("cameraInput");
const galleryInput  = document.getElementById("galleryInput");
const previewWrap   = document.getElementById("imagePreviewWrap");
const previewImg    = document.getElementById("imagePreview");
const fileNameSpan  = document.getElementById("imageFileName");
const clearBtn      = document.getElementById("clearImageBtn");

function handleImageFile(file) {
  if (!file) return;
  if (previewImg)   previewImg.src = URL.createObjectURL(file);
  if (fileNameSpan) fileNameSpan.textContent = file.name;
  if (previewWrap)  previewWrap.classList.add("visible");
  if (searchInput)  searchInput.placeholder = "Searching by image…";
  performImageSearch(file);
}

async function performImageSearch(file) {
  showSkeletons();
  currentResults = [];
  try {
    // Step 1: get a text query from the image
    const formData = new FormData();
    formData.append("image", file);
    const labelRes = await fetchWithTimeout("/api/image-search", 15000, {
      method: "POST",
      body: formData,
    });
    if (!labelRes.ok) throw new Error(`Image analysis failed: HTTP ${labelRes.status}`);
    const { query, error } = await labelRes.json();
    if (error) throw new Error(error);

    // Step 2: fill the search box and search
    if (searchInput) searchInput.value = query;
    if (searchInput) searchInput.placeholder = "Search for any product…";

    const res = await fetchWithTimeout(`/api/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    hideSkeletons();
    currentResults = data.results || [];
    if (currentResults.length === 0) {
      if (emptyState) emptyState.style.display = "flex";
      return;
    }
    renderPage();
  } catch (err) {
    hideSkeletons();
    if (errorState)   errorState.style.display = "flex";
    if (errorTitle)   errorTitle.textContent = "Image search failed";
    if (errorMessage) errorMessage.textContent = err.message || "Could not identify the product. Try typing a search instead.";
    console.error(err);
  }
}

if (cameraInput)  cameraInput.addEventListener("change",  e => handleImageFile(e.target.files[0]));
if (galleryInput) galleryInput.addEventListener("change", e => handleImageFile(e.target.files[0]));

if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    if (previewImg)   previewImg.src = "";
    if (fileNameSpan) fileNameSpan.textContent = "";
    if (previewWrap)  previewWrap.classList.remove("visible");
    if (cameraInput)  cameraInput.value = "";
    if (galleryInput) galleryInput.value = "";
    if (searchInput)  searchInput.placeholder = "Search for any product…";
  });
}

document.querySelectorAll(".example-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    if (searchInput) searchInput.value = chip.dataset.q || chip.textContent;
    performSearch();
  });
});

document.querySelectorAll(".platform-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".platform-chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    if (currentResults.length) renderPage();
  });
});

document.querySelectorAll(".sort-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    document.querySelectorAll(".sort-chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    if (currentResults.length) renderPage();
  });
});

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    themeToggle.querySelector(".icon-moon").style.display = document.body.classList.contains("dark") ? "none" : "";
    themeToggle.querySelector(".icon-sun").style.display  = document.body.classList.contains("dark") ? "" : "none";
  });
}

let currentResults = [];

function formatCurrency(price) {
  if (price == null) return "N/A";
  return "₹" + Number(price).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function platformColor(p) {
  p = (p || "").toLowerCase();
  if (p === "amazon")   return "#FF9900";
  if (p === "flipkart") return "#2874F0";
  if (p === "myntra")   return "#FF3F6C";
  if (p === "snapdeal") return "#E02020";
  return "#888";
}

function showSkeletons() {
  if (skeletonGrid) skeletonGrid.style.display = "grid";
  if (productGrid)  { productGrid.innerHTML = ""; productGrid.style.display = "none"; }
  if (emptyState)   emptyState.style.display = "none";
  if (errorState)   errorState.style.display = "none";
  if (controlsBar)  controlsBar.style.display = "none";
  if (statusBar)    statusBar.style.display = "none";
}

function hideSkeletons() {
  if (skeletonGrid) skeletonGrid.style.display = "none";
}

function fetchWithTimeout(url, ms = 12000, options = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { signal: ctrl.signal, ...options }).finally(() => clearTimeout(t));
}

function renderPage() {
  if (!productGrid) return;
  productGrid.innerHTML = "";

  const activePlatform = document.querySelector(".platform-chip.active")?.dataset.platform || "all";
  const activeSort = document.querySelector(".sort-chip.active")?.dataset.sort || "relevance";

  let filtered = activePlatform === "all"
    ? [...currentResults]
    : currentResults.filter(r => (r.platform || "").toLowerCase() === activePlatform);

  function getPrice(p) {
    if (p == null) return Infinity;
    const n = parseFloat(p);
    return isNaN(n) ? Infinity : n;
  }

  // Find the true lowest price across all filtered results first
  const lowestPrice = Math.min(...filtered.map(r => getPrice(r.price)));

  // Sort by user preference
  if (activeSort === "price_desc") filtered.sort((a, b) => getPrice(b.price) - getPrice(a.price));
  else if (activeSort === "rating") filtered.sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0));
  else filtered.sort((a, b) => getPrice(a.price) - getPrice(b.price));

  // Always move the best price item to position 0
  const bestIdx = filtered.findIndex(r => getPrice(r.price) === lowestPrice);
  if (bestIdx > 0) {
    const [best] = filtered.splice(bestIdx, 1);
    filtered.unshift(best);
  }

  if (filtered.length === 0) {
    if (emptyState) emptyState.style.display = "flex";
    productGrid.style.display = "none";
    return;
  }

  if (emptyState) emptyState.style.display = "none";
  productGrid.style.display = "grid";

  filtered.forEach(item => {
    const isBest = getPrice(item.price) === lowestPrice;
    const platform = (item.platform || "").toLowerCase();
    const card = document.createElement("div");
    card.className = "product-card" + (isBest ? " best-price" : "");

    const stripeColor = platformColor(item.platform);
    card.innerHTML = `
      <div class="card-stripe" style="background:${stripeColor}"></div>
      ${isBest ? '<div class="best-deal-badge">🏷️ Best Price</div>' : ""}
      <div class="card-img-wrap">
        ${item.image_url
          ? `<img src="${item.image_url}" alt="${item.title || 'Product'}" loading="lazy">`
          : `<div class="card-img-placeholder">🛍️</div>`}
      </div>
      <div class="card-body">
        <span class="card-platform ${platform}">${item.platform_logo || ""} ${item.platform || "?"}</span>
        <div class="card-title">${item.title || item.product_name || "Product"}</div>
        <div class="card-price-row">
          <div class="card-price"><span class="currency">₹</span>${Number(item.price).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</div>
        </div>
        ${item.rating ? `<div class="card-meta"><span class="card-rating">★ ${item.rating}</span>${item.review_count ? `<span>${item.review_count.toLocaleString()} reviews</span>` : ""}</div>` : ""}
      </div>
      ${item.url ? `<a href="${item.url}" target="_blank" rel="noopener noreferrer" class="card-cta">View on ${item.platform} <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></a>` : ""}
    `;
    productGrid.appendChild(card);
  });

  if (statusBar)   statusBar.style.display = "block";
  if (resultCount) resultCount.textContent = `${filtered.length} results`;
  if (controlsBar) controlsBar.style.display = "block";
}

async function performSearch() {
  const query = (searchInput?.value || "").trim();
  if (!query) return;
  showSkeletons();
  currentResults = [];
  try {
    const res = await fetchWithTimeout(`/api/search?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    hideSkeletons();
    currentResults = data.results || [];
    if (currentResults.length === 0) {
      if (emptyState) emptyState.style.display = "flex";
      return;
    }
    renderPage();
  } catch (err) {
    hideSkeletons();
    if (errorState)   errorState.style.display = "flex";
    if (errorTitle)   errorTitle.textContent = err.name === "AbortError" ? "Search timed out" : "Something went wrong";
    if (errorMessage) errorMessage.textContent = err.name === "AbortError" ? "Scrapers are taking too long. Please try again." : "Could not fetch prices. Please try again.";
    console.error(err);
  }
}

if (searchBtn)   searchBtn.addEventListener("click", performSearch);
if (searchInput) searchInput.addEventListener("keydown", e => { if (e.key === "Enter") performSearch(); });

