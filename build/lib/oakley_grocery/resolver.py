"""Product resolution pipeline — preferences, search, ranking, disambiguation."""

from __future__ import annotations

from typing import Optional

from oakley_grocery import db, woolworths
from oakley_grocery.common.config import Config


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase tokens for matching."""
    return set(text.lower().split()) if text else set()


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def _calculate_relevance(product: dict, generic_name: str,
                         prefer_brand: Optional[str] = None,
                         prefer_size: Optional[str] = None) -> float:
    """Score a product's relevance to a generic name. Returns 0.0-1.0.

    Weights:
    - Name token overlap (Jaccard): 40%
    - Brand match: 20%
    - Size match: 15%
    - Purchase history frequency: 15%
    - On special bonus: 5%
    - Availability penalty: halves score if unavailable
    """
    score = 0.0

    # Name overlap — 40%
    query_tokens = _tokenize(generic_name)
    name_tokens = _tokenize(product.get("name", ""))
    score += _jaccard(query_tokens, name_tokens) * 0.4

    # Brand match — 20%
    if prefer_brand:
        product_brand = (product.get("brand") or "").lower()
        if prefer_brand.lower() in product_brand or product_brand in prefer_brand.lower():
            score += 0.2
        elif product_brand:
            # Partial brand token match
            brand_overlap = _jaccard(_tokenize(prefer_brand), _tokenize(product_brand))
            score += brand_overlap * 0.2

    # Size match — 15%
    if prefer_size:
        product_size = (product.get("package_size") or "").lower()
        if prefer_size.lower() in product_size or product_size in prefer_size.lower():
            score += 0.15

    # Purchase history — 15%
    pref = db.get_preference(generic_name)
    if pref and pref.get("stockcode") == product.get("stockcode"):
        frequency_bonus = min(pref.get("purchase_count", 0) / 10, 1.0)
        score += frequency_bonus * 0.15

    # On special bonus — 5%
    if product.get("on_special"):
        score += 0.05

    # Availability penalty
    if not product.get("available", True):
        score *= 0.5

    return min(score, 1.0)


def resolve_item(generic_name: str, quantity: int = 1,
                 prefer_brand: Optional[str] = None,
                 prefer_size: Optional[str] = None) -> dict:
    """Resolve a generic item name to a specific Woolworths product.

    Returns:
        {
            "resolved": bool,
            "product": dict or None,
            "candidates": list[dict],
            "source": "preference"|"search"|"unresolved",
            "generic_name": str,
            "quantity": int,
        }
    """
    generic = generic_name.lower().strip()

    # 1. Exact preference match
    pref = db.get_preference(generic)
    if pref:
        return {
            "resolved": True,
            "product": {
                "stockcode": pref["stockcode"],
                "name": pref["product_name"],
                "brand": pref.get("brand"),
                "package_size": pref.get("package_size"),
                "price": pref.get("last_price"),
            },
            "candidates": [],
            "source": "preference",
            "generic_name": generic,
            "quantity": quantity,
        }

    # 2. Fuzzy preference match — check if any saved preferences overlap
    all_prefs = db.get_all_preferences()
    for p in all_prefs:
        pref_tokens = _tokenize(p["generic_name"])
        query_tokens = _tokenize(generic)
        overlap = _jaccard(query_tokens, pref_tokens)
        if overlap >= 0.6:
            return {
                "resolved": True,
                "product": {
                    "stockcode": p["stockcode"],
                    "name": p["product_name"],
                    "brand": p.get("brand"),
                    "package_size": p.get("package_size"),
                    "price": p.get("last_price"),
                },
                "candidates": [],
                "source": "preference",
                "generic_name": generic,
                "quantity": quantity,
            }

    # 3. Woolworths search + rank
    try:
        search_query = generic
        if prefer_brand:
            search_query = f"{prefer_brand} {generic}"
        if prefer_size:
            search_query = f"{search_query} {prefer_size}"

        products = woolworths.search_products(search_query, page_size=10)
    except RuntimeError:
        return {
            "resolved": False,
            "product": None,
            "candidates": [],
            "source": "unresolved",
            "generic_name": generic,
            "quantity": quantity,
        }

    if not products:
        return {
            "resolved": False,
            "product": None,
            "candidates": [],
            "source": "unresolved",
            "generic_name": generic,
            "quantity": quantity,
        }

    # Score each product
    scored = []
    for p in products:
        score = _calculate_relevance(p, generic, prefer_brand, prefer_size)
        scored.append({**p, "_score": score})

    scored.sort(key=lambda x: x["_score"], reverse=True)

    top = scored[0]
    second = scored[1] if len(scored) > 1 else None

    # 4. Auto-resolve vs disambiguate
    gap = (top["_score"] - second["_score"]) if second else 1.0

    if top["_score"] >= Config.auto_resolve_min_score and gap >= Config.auto_resolve_gap:
        return {
            "resolved": True,
            "product": top,
            "candidates": scored[:5],
            "source": "search",
            "generic_name": generic,
            "quantity": quantity,
        }

    return {
        "resolved": False,
        "product": None,
        "candidates": scored[:5],
        "source": "unresolved",
        "generic_name": generic,
        "quantity": quantity,
    }


def resolve_list(items: list[dict]) -> list[dict]:
    """Batch resolve a list of items.

    Each item should have at least: {"generic_name": str}
    Optional: quantity, prefer_brand, prefer_size
    """
    results = []
    for item in items:
        result = resolve_item(
            generic_name=item["generic_name"],
            quantity=item.get("quantity", 1),
            prefer_brand=item.get("prefer_brand"),
            prefer_size=item.get("prefer_size"),
        )
        results.append(result)
    return results


def learn_preference(generic_name: str, stockcode: int, product_name: str,
                     brand: Optional[str] = None, package_size: Optional[str] = None,
                     price: Optional[float] = None) -> int:
    """Save a product preference for future resolution. Returns preference id."""
    return db.save_preference(
        generic_name=generic_name,
        stockcode=stockcode,
        product_name=product_name,
        brand=brand,
        package_size=package_size,
        price=price,
    )
