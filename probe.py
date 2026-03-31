import httpx, asyncio, re, json

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

async def get(url):
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as c:
        return (await c.get(url, headers=HEADERS)).text

def extract_json_object(html, marker):
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find('{', idx)
    depth = 0
    for i, ch in enumerate(html[start:], start):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try: return json.loads(html[start:i+1])
                except: return None
    return None

async def main():
    # Nykaa - full first product
    print("=== NYKAA first product ===")
    html = await get("https://www.nykaa.com/search/result/?q=lipstick")
    d = extract_json_object(html, "window.__PRELOADED_STATE__ =")
    prods = d["categoryListing"]["listingData"]["products"]
    print(json.dumps(prods[0], indent=2)[:1200])

    # Meesho - check listing.products directly
    print("\n=== MEESHO listing.products ===")
    html = await get("https://www.meesho.com/search?q=iphone")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    d = json.loads(m.group(1))
    listing = d["props"]["pageProps"]["initialState"]["searchListing"]["listing"]
    products = listing.get("products", [])
    print(f"products type={type(products).__name__} len={len(products) if isinstance(products, list) else 'N/A'}")
    if isinstance(products, list) and products:
        print(json.dumps(products[0], indent=2)[:800])
    else:
        print(f"products value: {str(products)[:300]}")
        # check pages
        pages = listing.get("pages", {})
        print(f"\npages: {json.dumps(pages, indent=2)[:400]}")

asyncio.run(main())