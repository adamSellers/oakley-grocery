"""Cart builder — build Woolworths trolley from shopping lists."""

from __future__ import annotations

import sys

from oakley_grocery import db, woolworths
from oakley_grocery.common.formatting import format_price


def build_cart(list_id: int, confirm: bool = False) -> dict:
    """Build a Woolworths cart from a shopping list.

    Without --confirm: returns preview.
    With --confirm: adds items to Woolworths trolley via API.

    Returns:
        {
            "success": bool,
            "preview": bool,
            "items": list[dict],
            "total_estimate": float,
            "added": int,
            "failed": list[dict],
            "message": str,
        }
    """
    lst = db.get_list(list_id)
    if not lst:
        return {"success": False, "message": f"List {list_id} not found"}

    if lst["status"] != "active":
        return {"success": False, "message": f"List is {lst['status']}, not active"}

    items = db.get_list_items(list_id)
    if not items:
        return {"success": False, "message": "List is empty"}

    # Check which items are resolved
    resolved = [i for i in items if i.get("resolved") and i.get("stockcode")]
    unresolved = [i for i in items if not i.get("resolved") or not i.get("stockcode")]

    if not resolved:
        return {
            "success": False,
            "message": f"No resolved items. Run: oakley-grocery list-show --list-id {list_id} --resolve",
        }

    total = sum((i.get("price") or 0) * i.get("quantity", 1) for i in resolved)

    cart_items = []
    for item in resolved:
        cart_items.append({
            "generic_name": item["generic_name"],
            "stockcode": item["stockcode"],
            "product_name": item.get("product_name", item["generic_name"]),
            "quantity": item.get("quantity", 1),
            "price": item.get("price"),
        })

    if not confirm:
        return {
            "success": True,
            "preview": True,
            "items": cart_items,
            "unresolved": [i["generic_name"] for i in unresolved],
            "total_estimate": total,
            "added": 0,
            "failed": [],
            "message": f"{len(cart_items)} items, est. {format_price(total)}. Run with --confirm to build cart.",
        }

    # Validate session first
    session = woolworths.validate_session()
    if not session.get("valid"):
        return {
            "success": False,
            "message": f"Woolworths session invalid: {session.get('error', 'unknown')}. Update cookies with: oakley-grocery setup --woolworths-cookies COOKIES",
        }

    # Add items to trolley
    added = 0
    failed = []
    for item in cart_items:
        try:
            woolworths.add_to_trolley(item["stockcode"], item["quantity"])
            added += 1
        except RuntimeError as e:
            failed.append({
                "generic_name": item["generic_name"],
                "stockcode": item["stockcode"],
                "error": str(e),
            })

    return {
        "success": True,
        "preview": False,
        "items": cart_items,
        "unresolved": [i["generic_name"] for i in unresolved],
        "total_estimate": total,
        "added": added,
        "failed": failed,
        "message": f"Cart built. {added} items added. Open woolworths.com.au/shop/checkout",
    }


def get_cart_status() -> dict:
    """Get current Woolworths trolley contents.

    Returns:
        {
            "success": bool,
            "items": list[dict],
            "total": float,
            "message": str,
        }
    """
    try:
        data = woolworths.get_trolley()
    except RuntimeError as e:
        return {"success": False, "items": [], "total": 0, "message": str(e)}

    items = []
    total = 0.0

    trolley_items = data.get("TrolleyItems", data.get("Items", []))
    for ti in trolley_items:
        price = ti.get("SalePrice", ti.get("Price", 0))
        qty = ti.get("Quantity", 1)
        item_total = price * qty
        total += item_total

        items.append({
            "stockcode": ti.get("Stockcode"),
            "name": ti.get("DisplayName", ti.get("Name", "Unknown")),
            "quantity": qty,
            "price": price,
            "total": item_total,
        })

    return {
        "success": True,
        "items": items,
        "total": total,
        "message": f"{len(items)} items in trolley, total {format_price(total)}",
    }
