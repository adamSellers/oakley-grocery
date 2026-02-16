"""Dan Murphy's web API client — product search."""

from __future__ import annotations

from typing import Optional

import requests

from oakley_grocery.common.config import Config
from oakley_grocery.common.cache import FileCache
from oakley_grocery.common.rate_limiter import RateLimiter

_cache = FileCache("danmurphys")
_limiter = RateLimiter(
    max_calls=Config.danmurphys_rate_limit_calls,
    period=Config.danmurphys_rate_limit_period,
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-AU,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": Config.danmurphys_homepage_url,
    "Referer": f"{Config.danmurphys_homepage_url}/search",
}

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Get or create a requests session with Cloudflare cookies.

    Dan Murphy's uses Cloudflare which requires valid session cookies
    obtained from an initial page load.
    """
    global _session
    if _session is not None:
        return _session

    _session = requests.Session()
    _session.headers.update(_HEADERS)

    # Hit homepage to acquire Cloudflare cookies
    try:
        _session.get(
            f"{Config.danmurphys_homepage_url}/",
            timeout=Config.request_timeout,
        )
    except requests.RequestException:
        pass  # Proceed anyway — might still work from cache

    return _session


def _reset_session() -> None:
    """Reset session (e.g. after auth failure)."""
    global _session
    _session = None


def _extract_detail(details: list[dict], key: str) -> str:
    """Extract a value from the AdditionalDetails array by key name."""
    if not details:
        return ""
    for detail in details:
        if detail.get("Name", "").lower() == key.lower():
            val = detail.get("Value", "")
            if isinstance(val, bool):
                return ""
            return str(val) if val else ""
    return ""


def _parse_product(raw: dict) -> dict:
    """Normalise a Dan Murphy's product response into a clean dict."""
    # Price extraction — Dan Murphy's has 3 tiers
    price_obj = raw.get("Price", {}) or {}

    single_price = None
    six_price = None
    case_price = None
    was_price = None
    is_member_offer = False

    if isinstance(price_obj, dict):
        single_raw = price_obj.get("singleprice", {}) or {}
        six_raw = price_obj.get("inanysixprice", {}) or {}
        case_raw = price_obj.get("caseprice", {}) or {}

        single_price = single_raw.get("Value")
        six_price = six_raw.get("Value")
        case_price = case_raw.get("Value")

        was_price = single_raw.get("BeforePromotion")
        is_member_offer = single_raw.get("IsMemberOffer", False)
    elif isinstance(price_obj, (int, float)):
        single_price = price_obj

    on_special = raw.get("IsSpecial", False)
    amount_saved = raw.get("AmountSaved")

    # Additional details
    details = raw.get("AdditionalDetails", []) or []

    return {
        "stockcode": raw.get("Stockcode"),
        "name": raw.get("Title", raw.get("Name", "")),
        "brand": raw.get("Brand", ""),
        "volume": raw.get("VolumeSize", ""),
        # Pricing — 3 tiers
        "price": single_price,
        "six_price": six_price,
        "case_price": case_price,
        "was_price": was_price if on_special else None,
        "on_special": on_special,
        "amount_saved": amount_saved,
        "is_member_offer": is_member_offer,
        # Alcohol details
        "varietal": _extract_detail(details, "varietal"),
        "region": _extract_detail(details, "webregionoforigin"),
        "alcohol_pct": _extract_detail(details, "webalcoholpercentage"),
        "rating": _extract_detail(details, "webaverageproductrating"),
        "review_count": _extract_detail(details, "webtotalreviewcount"),
        "wine_body": _extract_detail(details, "webwinebody"),
        "category": _extract_detail(details, "webmaincategory"),
        "description": _extract_detail(details, "webdescriptionshort"),
        # Common
        "image_url": raw.get("ImageFile", ""),
        "store": "dan-murphys",
    }


def search_products(query: str, page: int = 1, page_size: int = 0,
                    sort_by: str = "") -> list[dict]:
    """Search Dan Murphy's products. Returns list of normalised product dicts."""
    if not page_size:
        page_size = Config.danmurphys_default_page_size
    if not sort_by:
        sort_by = Config.danmurphys_default_sort

    cache_key = f"dm_search_{query}_{page}_{page_size}_{sort_by}"
    cached = _cache.get(cache_key, ttl=Config.cache_ttl["danmurphys_search"])
    if cached:
        return cached

    _limiter.acquire()
    session = _get_session()

    payload = {
        "Filters": [],
        "SearchTerm": query,
        "PageSize": page_size,
        "PageNumber": page,
        "SortType": sort_by,
        "Location": "ListerFacet",
        "PageUrl": f"/{query.lower().replace(' ', '-')}",
    }

    try:
        resp = session.post(
            Config.danmurphys_search_url,
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
        raise RuntimeError(f"Dan Murphy's search failed: {e}") from e

    products = []
    bundles = data.get("Products", [])
    for bundle in bundles:
        items = bundle.get("Products", [])
        for item in items:
            products.append(_parse_product(item))

    _cache.set(cache_key, products)
    return products


def test_connection() -> dict:
    """Test Dan Murphy's API connectivity with a simple search."""
    try:
        results = search_products("shiraz", page_size=1)
        if results:
            return {"connected": True}
        return {"connected": True, "note": "No results but API responded"}
    except Exception as e:
        return {"connected": False, "error": str(e)}
