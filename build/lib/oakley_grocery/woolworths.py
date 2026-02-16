"""Woolworths web API client — product search, details, specials, trolley."""

from __future__ import annotations

from typing import Optional

import requests

from oakley_grocery.common.config import Config
from oakley_grocery.common.cache import FileCache
from oakley_grocery.common.rate_limiter import RateLimiter
from oakley_grocery import auth

_cache = FileCache("woolworths")
_limiter = RateLimiter(
    max_calls=Config.woolworths_rate_limit_calls,
    period=Config.woolworths_rate_limit_period,
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": Config.woolworths_base_url,
    "Referer": f"{Config.woolworths_base_url}/shop/search/products",
}

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Get or create a requests session with Woolworths bot-manager cookies.

    Woolworths uses Akamai Bot Manager which requires valid session cookies
    (_abck, bm_s, etc.) obtained from an initial page load.
    """
    global _session
    if _session is not None:
        return _session

    _session = requests.Session()
    _session.headers.update(_HEADERS)

    # Hit homepage to acquire bot-manager cookies
    try:
        _session.get(
            f"{Config.woolworths_base_url}/",
            timeout=Config.request_timeout,
        )
    except requests.RequestException:
        pass  # Proceed anyway — might still work from cache

    return _session


def _reset_session() -> None:
    """Reset session (e.g. after auth failure)."""
    global _session
    _session = None


def _parse_product(raw: dict) -> dict:
    """Normalise a Woolworths product response into a clean dict."""
    price = raw.get("Price") or raw.get("InstorePrice")
    was_price = raw.get("WasPrice")
    on_special = raw.get("IsOnSpecial", False) or raw.get("IsInStoreSpecial", False)

    cup_price_str = raw.get("CupString", "")
    cup_price = raw.get("CupPrice")

    package_size = raw.get("PackageSize", "") or raw.get("Unit", "")

    return {
        "stockcode": raw.get("Stockcode"),
        "name": raw.get("Name", raw.get("DisplayName", "")),
        "brand": raw.get("Brand", ""),
        "price": price,
        "was_price": was_price if on_special else None,
        "cup_price": cup_price,
        "cup_string": cup_price_str,
        "package_size": package_size,
        "available": raw.get("IsAvailable", True),
        "on_special": on_special,
        "image_url": raw.get("MediumImageFile", raw.get("SmallImageFile", "")),
        "aisle": raw.get("Aisle", ""),
        "description": raw.get("Description", ""),
    }


def search_products(query: str, page: int = 1, page_size: int = 0,
                    sort_by: str = "") -> list[dict]:
    """Search Woolworths products. Returns list of normalised product dicts."""
    if not page_size:
        page_size = Config.default_page_size
    if not sort_by:
        sort_by = Config.default_sort

    cache_key = f"search_{query}_{page}_{page_size}_{sort_by}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["search"])
    if cached:
        return cached

    _limiter.acquire()
    session = _get_session()

    payload = {
        "SearchTerm": query,
        "PageNumber": page,
        "PageSize": page_size,
        "SortType": sort_by,
        "Location": "",
        "IsSpecial": False,
    }

    try:
        resp = session.post(
            Config.woolworths_search_url,
            json=payload,
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        # Reset session and try stale cache
        _reset_session()
        stale = _cache.get(cache_key)
        if stale:
            return stale
        raise RuntimeError(f"Woolworths search failed: {e}") from e

    products = []
    bundles = data.get("Products", [])
    for bundle in bundles:
        items = bundle.get("Products", [])
        for item in items:
            products.append(_parse_product(item))

    _cache.set(cache_key, products)
    return products


def get_product_details(stockcode: int) -> Optional[dict]:
    """Get detailed product info by stockcode."""
    cache_key = f"product_{stockcode}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["product"])
    if cached:
        return cached

    _limiter.acquire()
    session = _get_session()

    try:
        resp = session.get(
            f"{Config.woolworths_product_url}/{stockcode}",
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        _reset_session()
        stale = _cache.get(cache_key)
        if stale:
            return stale
        raise RuntimeError(f"Woolworths product detail failed: {e}") from e

    product = _parse_product(data.get("Product", data))
    _cache.set(cache_key, product)
    return product


def get_specials(page: int = 1, page_size: int = 20) -> list[dict]:
    """Get current specials."""
    cache_key = f"specials_{page}_{page_size}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["specials"])
    if cached:
        return cached

    _limiter.acquire()
    session = _get_session()

    payload = {
        "SearchTerm": "",
        "PageNumber": page,
        "PageSize": page_size,
        "SortType": "TraderRelevance",
        "Location": "",
        "IsSpecial": True,
    }

    try:
        resp = session.post(
            Config.woolworths_search_url,
            json=payload,
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        _reset_session()
        stale = _cache.get(cache_key)
        if stale:
            return stale
        raise RuntimeError(f"Woolworths specials failed: {e}") from e

    products = []
    bundles = data.get("Products", [])
    for bundle in bundles:
        items = bundle.get("Products", [])
        for item in items:
            parsed = _parse_product(item)
            if parsed.get("on_special"):
                products.append(parsed)

    _cache.set(cache_key, products)
    return products


# ─── Trolley (cart) operations — require cookies ─────────────────────────────

def _get_trolley_headers() -> dict:
    """Build headers with cookie auth for trolley operations."""
    cookies = auth.get_woolworths_cookies()
    if not cookies:
        raise RuntimeError("Woolworths cookies not configured. Run: oakley-grocery setup --woolworths-cookies COOKIES")
    headers = dict(_HEADERS)
    headers["Cookie"] = cookies
    return headers


def add_to_trolley(stockcode: int, quantity: int = 1) -> dict:
    """Add a product to the Woolworths trolley. Returns API response."""
    _limiter.acquire()
    headers = _get_trolley_headers()

    payload = {
        "Stockcode": stockcode,
        "Quantity": quantity,
    }

    try:
        resp = requests.post(
            Config.woolworths_trolley_url,
            json=payload,
            headers=headers,
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to add to trolley: {e}") from e


def get_trolley() -> dict:
    """Get current trolley contents."""
    cache_key = "trolley_current"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["trolley"])
    if cached:
        return cached

    _limiter.acquire()
    headers = _get_trolley_headers()

    try:
        resp = requests.get(
            Config.woolworths_trolley_list_url,
            headers=headers,
            timeout=Config.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        stale = _cache.get(cache_key)
        if stale:
            return stale
        raise RuntimeError(f"Failed to get trolley: {e}") from e

    _cache.set(cache_key, data)
    return data


def validate_session() -> dict:
    """Check if cookies are still valid by attempting a trolley fetch."""
    try:
        get_trolley()
        return {"valid": True}
    except RuntimeError as e:
        return {"valid": False, "error": str(e)}


def test_connection() -> dict:
    """Test Woolworths API connectivity with a simple search."""
    try:
        results = search_products("milk", page_size=1)
        if results:
            return {"connected": True}
        return {"connected": True, "note": "No results but API responded"}
    except Exception as e:
        return {"connected": False, "error": str(e)}
