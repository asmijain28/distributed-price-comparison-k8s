/**
 * PriceRadar v2 — Frontend Application
 */
(function () {
    'use strict';

    // ── DOM refs ────────────────────────────────────────────────
    const searchInput   = document.getElementById('searchInput');
    const searchBtn     = document.getElementById('searchBtn');
    const btnText       = searchBtn.querySelector('.btn-text');
    const btnSpinner    = searchBtn.querySelector('.btn-spinner');
    const controlsBar   = document.getElementById('controlsBar');
    const statusBar     = document.getElementById('statusBar');
    const resultCount   = document.getElementById('resultCount');
    const cacheStatus   = document.getElementById('cacheStatus');
    const productGrid   = document.getElementById('productGrid');
    const skeletonGrid  = document.getElementById('skeletonGrid');
    const emptyState    = document.getElementById('emptyState');
    const errorState    = document.getElementById('errorState');
    const errorMessage  = document.getElementById('errorMessage');
    const toastContainer= document.getElementById('toastContainer');
    const pagination    = document.getElementById('pagination');
    const prevPage      = document.getElementById('prevPage');
    const nextPage      = document.getElementById('nextPage');
    const pageInfo      = document.getElementById('pageInfo');
    const themeToggle   = document.getElementById('themeToggle');
    const iconMoon      = themeToggle.querySelector('.icon-moon');
    const iconSun       = themeToggle.querySelector('.icon-sun');

    // ── State ───────────────────────────────────────────────────
    let currentQuery   = '';
    let currentSort    = 'relevance';
    let activePlatforms = new Set();
    let currentPage    = 1;
    const PAGE_LIMIT   = 20;
    let totalResults   = 0;
    let isLoading      = false;

    // Platform stripe colours
    const PLATFORM_COLORS = {
        amazon:   '#FF9900',
        flipkart: '#2874F0',
        myntra:   '#FF3F6C',
        snapdeal: '#E02020',
    };

    // ── Theme ───────────────────────────────────────────────────
    function initTheme() {
        const saved = localStorage.getItem('priceradar-theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (saved === 'dark' || (!saved && prefersDark)) {
            document.documentElement.setAttribute('data-theme', 'dark');
            iconMoon.style.display = 'none';
            iconSun.style.display  = '';
        }
    }
    initTheme();

    themeToggle.addEventListener('click', function () {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        if (isDark) {
            document.documentElement.removeAttribute('data-theme');
            iconMoon.style.display = '';
            iconSun.style.display  = 'none';
            localStorage.setItem('priceradar-theme', 'light');
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            iconMoon.style.display = 'none';
            iconSun.style.display  = '';
            localStorage.setItem('priceradar-theme', 'dark');
        }
    });

    // ── Search ──────────────────────────────────────────────────
    function doSearch() {
        const q = searchInput.value.trim();
        if (!q || isLoading) return;
        currentQuery = q;
        currentPage  = 1;
        fetchResults();
    }

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });

    document.querySelectorAll('.example-chip').forEach(chip => {
        chip.addEventListener('click', function () {
            searchInput.value = this.dataset.q;
            doSearch();
        });
    });

    // ── Platform chips ──────────────────────────────────────────
    document.querySelectorAll('.platform-chip').forEach(chip => {
        chip.addEventListener('click', function () {
            const plat = this.dataset.platform;
            const allBtn = document.querySelector('.platform-chip[data-platform="all"]');
            if (plat === 'all') {
                activePlatforms.clear();
                document.querySelectorAll('.platform-chip').forEach(c => c.classList.remove('active'));
                this.classList.add('active');
            } else {
                allBtn.classList.remove('active');
                if (activePlatforms.has(plat)) {
                    activePlatforms.delete(plat);
                    this.classList.remove('active');
                } else {
                    activePlatforms.add(plat);
                    this.classList.add('active');
                }
                if (activePlatforms.size === 0) allBtn.classList.add('active');
            }
            if (currentQuery) { currentPage = 1; fetchResults(); }
        });
    });

    // ── Sort chips ──────────────────────────────────────────────
    document.querySelectorAll('.sort-chip').forEach(chip => {
        chip.addEventListener('click', function () {
            document.querySelectorAll('.sort-chip').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            currentSort = this.dataset.sort;
            if (currentQuery) { currentPage = 1; fetchResults(); }
        });
    });

    // ── Pagination ──────────────────────────────────────────────
    prevPage.addEventListener('click', () => { if (currentPage > 1) { currentPage--; fetchResults(); } });
    nextPage.addEventListener('click', () => { if (currentPage * PAGE_LIMIT < totalResults) { currentPage++; fetchResults(); } });

    // ── Fetch ───────────────────────────────────────────────────
    async function fetchResults() {
        if (isLoading) return;
        isLoading = true;

        showSkeleton();
        hideStates();
        controlsBar.style.display = '';
        searchBtn.disabled = true;
        btnText.style.display   = 'none';
        btnSpinner.style.display = '';

        const params = new URLSearchParams({
            q:     currentQuery,
            sort:  currentSort,
            page:  String(currentPage),
            limit: String(PAGE_LIMIT),
        });
        if (activePlatforms.size > 0) {
            params.set('platform', Array.from(activePlatforms).join(','));
        }

        try {
            const resp = await fetch('/api/search?' + params.toString());
            const data = await resp.json();

            if (!resp.ok) { showError(data.error || 'Something went wrong'); return; }

            totalResults = data.total_results || 0;
            const results = data.results || [];
            const errors  = data.scraper_errors || [];

            errors.forEach(err => showToast(err.source + ': ' + err.message));

            statusBar.style.display = '';
            resultCount.textContent = `${totalResults} result${totalResults !== 1 ? 's' : ''} for "${currentQuery}"`;
            cacheStatus.textContent = data.cached ? '⚡ Cached' : '🔄 Live';

            if (results.length === 0) {
                showEmpty();
            } else {
                renderProducts(results);
                updatePagination();
            }
        } catch (err) {
            showError('Network error — could not reach the server.');
            console.error(err);
        } finally {
            isLoading = false;
            searchBtn.disabled   = false;
            btnText.style.display    = '';
            btnSpinner.style.display = 'none';
            hideSkeleton();
        }
    }

    // ── Render ──────────────────────────────────────────────────
    function renderProducts(results) {
        let minPrice = Infinity, minIdx = -1;
        results.forEach((r, i) => { if (r.price < minPrice) { minPrice = r.price; minIdx = i; } });

        const html = results.map((r, i) => {
            const key   = (r.platform || '').toLowerCase().replace(/\s+/g, '');
            const color = PLATFORM_COLORS[key] || '#5B4CF5';
            const best  = i === minIdx && results.length > 1;

            return `
<div class="product-card">
  <div class="card-stripe" style="background:${color}"></div>
  ${best ? '<div class="best-deal-badge">Best Deal</div>' : ''}
  <div class="card-img-wrap">
    ${r.image_url
        ? `<img src="${escAttr(r.image_url)}" alt="${escAttr(r.title)}" loading="lazy">`
        : '<div class="card-img-placeholder">📦</div>'}
  </div>
  <div class="card-body">
    <span class="card-platform ${key}" style="background:${color}">${escHtml(r.platform_logo || '🛒')} ${escHtml(r.platform)}</span>
    <div class="card-title" title="${escAttr(r.title)}">${escHtml(r.title)}</div>
    <div class="card-price-row">
      <div class="card-price"><span class="currency">₹</span>${fmtPrice(r.price)}</div>
    </div>
    <div class="card-meta">
      ${r.rating ? `<span class="card-rating">★ ${Number(r.rating).toFixed(1)}</span>` : ''}
      ${r.review_count ? `<span>${fmtCount(r.review_count)} reviews</span>` : ''}
    </div>
  </div>
  <a href="${escAttr(r.url)}" target="_blank" rel="noopener" class="card-cta">
    View Deal
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
  </a>
</div>`;
        }).join('');

        productGrid.innerHTML = html;
        productGrid.style.display = '';
    }

    // ── Helpers ─────────────────────────────────────────────────
    function fmtPrice(n) { return Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 }); }
    function fmtCount(n) { return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n); }
    function escHtml(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
    function escAttr(s) { return (s || '').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

    function showSkeleton()  { skeletonGrid.style.display = ''; }
    function hideSkeleton()  { skeletonGrid.style.display = 'none'; }
    function hideStates() {
        emptyState.style.display  = 'none';
        errorState.style.display  = 'none';
        productGrid.innerHTML     = '';
        pagination.style.display  = 'none';
    }
    function showEmpty() {
        emptyState.style.display = '';
        productGrid.style.display = 'none';
        pagination.style.display  = 'none';
    }
    function showError(msg) {
        errorState.style.display  = '';
        errorMessage.textContent  = msg;
        productGrid.style.display = 'none';
        pagination.style.display  = 'none';
        statusBar.style.display   = 'none';
    }
    function updatePagination() {
        const totalPages = Math.ceil(totalResults / PAGE_LIMIT);
        if (totalPages <= 1) { pagination.style.display = 'none'; return; }
        pagination.style.display = '';
        prevPage.disabled = currentPage <= 1;
        nextPage.disabled = currentPage >= totalPages;
        pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    }
    function showToast(message) {
        const t = document.createElement('div');
        t.className = 'toast';
        t.textContent = '⚠️ ' + message;
        toastContainer.appendChild(t);
        setTimeout(() => {
            t.style.transition = 'opacity 0.3s';
            t.style.opacity = '0';
            setTimeout(() => t.remove(), 300);
        }, 5000);
    }
})();
