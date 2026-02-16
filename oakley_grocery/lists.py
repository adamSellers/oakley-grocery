"""Shopping list engine — create, manage, resolve, complete."""

from __future__ import annotations

from typing import Optional

from oakley_grocery import db
from oakley_grocery.resolver import resolve_item


def create_list(name: str, items: Optional[list[str]] = None) -> dict:
    """Create a new shopping list with optional initial items.

    Args:
        name: List name (e.g. "Weekly Shop 16 Feb")
        items: Optional list of item strings. Each can be "qty item" or just "item".

    Returns:
        {"list_id": int, "name": str, "item_count": int}
    """
    list_id = db.create_list(name)
    item_count = 0

    if items:
        for item_str in items:
            generic_name, quantity = _parse_item_string(item_str)
            db.add_list_item(list_id, generic_name, quantity)
            item_count += 1

    return {"list_id": list_id, "name": name, "item_count": item_count}


def add_items(list_id: int, items: list[str]) -> dict:
    """Add items to an existing list.

    Args:
        list_id: List ID
        items: List of item strings. Duplicates merge quantities.

    Returns:
        {"added": int, "merged": int}
    """
    lst = db.get_list(list_id)
    if not lst:
        raise ValueError(f"List {list_id} not found")
    if lst["status"] != "active":
        raise ValueError(f"List {list_id} is {lst['status']}, not active")

    existing = {item["generic_name"] for item in db.get_list_items(list_id)}
    added = 0
    merged = 0

    for item_str in items:
        generic_name, quantity = _parse_item_string(item_str)
        if generic_name in existing:
            merged += 1
        else:
            added += 1
        db.add_list_item(list_id, generic_name, quantity)
        existing.add(generic_name)

    return {"added": added, "merged": merged}


def remove_items(list_id: int, item_names: list[str]) -> dict:
    """Remove items from a list.

    Returns:
        {"removed": int, "not_found": list[str]}
    """
    lst = db.get_list(list_id)
    if not lst:
        raise ValueError(f"List {list_id} not found")

    removed = 0
    not_found = []

    for name in item_names:
        if db.remove_list_item(list_id, name):
            removed += 1
        else:
            not_found.append(name)

    return {"removed": removed, "not_found": not_found}


def get_list(list_id: int, resolve: bool = False) -> dict:
    """Get a list with its items, optionally resolving unresolved ones.

    Returns:
        {"list": dict, "items": list[dict], "stats": dict}
    """
    lst = db.get_list(list_id)
    if not lst:
        raise ValueError(f"List {list_id} not found")

    items = db.get_list_items(list_id)

    if resolve:
        stats = _resolve_list_items(list_id, items)
        items = db.get_list_items(list_id)  # Reload after resolution
    else:
        resolved = sum(1 for i in items if i["resolved"])
        stats = {
            "total": len(items),
            "resolved": resolved,
            "unresolved": len(items) - resolved,
        }

    # Calculate total estimate
    total = 0.0
    for item in items:
        if item.get("price") is not None:
            total += item["price"] * item.get("quantity", 1)

    if total > 0:
        db.update_list_status(list_id, lst["status"], total_estimate=total)

    return {"list": lst, "items": items, "stats": stats, "total_estimate": total}


def resolve_list_items(list_id: int) -> dict:
    """Resolve all unresolved items in a list. Returns stats."""
    lst = db.get_list(list_id)
    if not lst:
        raise ValueError(f"List {list_id} not found")

    items = db.get_list_items(list_id)
    return _resolve_list_items(list_id, items)


def _resolve_list_items(list_id: int, items: list[dict]) -> dict:
    """Internal: resolve unresolved items in a list."""
    resolved = 0
    already_resolved = 0
    unresolved = 0
    disambiguation_needed = []

    for item in items:
        if item["resolved"]:
            already_resolved += 1
            continue

        result = resolve_item(item["generic_name"])

        if result["resolved"] and result["product"]:
            product = result["product"]
            db.update_list_item(
                item["id"],
                stockcode=product.get("stockcode"),
                product_name=product.get("name"),
                price=product.get("price"),
                resolved=1,
            )
            resolved += 1
        elif result["candidates"]:
            disambiguation_needed.append({
                "item": item["generic_name"],
                "candidates": [
                    {
                        "stockcode": c.get("stockcode"),
                        "name": c.get("name"),
                        "brand": c.get("brand", ""),
                        "price": c.get("price"),
                        "package_size": c.get("package_size", ""),
                    }
                    for c in result["candidates"][:3]
                ],
            })
            unresolved += 1
        else:
            unresolved += 1

    return {
        "total": len(items),
        "resolved": resolved,
        "already_resolved": already_resolved,
        "unresolved": unresolved,
        "disambiguation_needed": disambiguation_needed,
    }


def mark_purchased(list_id: int, total_paid: Optional[float] = None,
                   notes: Optional[str] = None) -> dict:
    """Mark a list as purchased. Logs to order history and updates preferences.

    Returns:
        {"order_id": int, "items_logged": int}
    """
    lst = db.get_list(list_id)
    if not lst:
        raise ValueError(f"List {list_id} not found")

    items = db.get_list_items(list_id)
    total_estimate = sum(
        (i.get("price") or 0) * i.get("quantity", 1)
        for i in items
    )

    # Create order
    order_id = db.create_order(
        list_id=list_id,
        total_estimate=total_estimate if total_estimate > 0 else None,
        total_paid=total_paid,
        item_count=len(items),
        notes=notes,
    )

    # Log each item to order_items
    items_logged = 0
    for item in items:
        if item.get("stockcode"):
            db.add_order_item(
                order_id=order_id,
                generic_name=item["generic_name"],
                stockcode=item["stockcode"],
                product_name=item.get("product_name"),
                brand=None,  # TODO: could track brand in list_items
                quantity=item.get("quantity", 1),
                price=item.get("price"),
                on_special=False,
            )

            # Update preference purchase count
            db.save_preference(
                generic_name=item["generic_name"],
                stockcode=item["stockcode"],
                product_name=item.get("product_name") or item["generic_name"],
                price=item.get("price"),
            )

            # Record price history
            if item.get("price") is not None:
                db.record_price(
                    stockcode=item["stockcode"],
                    product_name=item.get("product_name") or item["generic_name"],
                    price=item["price"],
                )

            items_logged += 1

    # Mark list as purchased
    db.update_list_status(list_id, "purchased", total_estimate=total_estimate)

    return {"order_id": order_id, "items_logged": items_logged}


def _parse_item_string(item_str: str) -> tuple[str, int]:
    """Parse an item string like '2 milk' or 'bread' into (name, quantity)."""
    item_str = item_str.strip()
    parts = item_str.split(None, 1)

    if len(parts) == 2:
        try:
            quantity = int(parts[0])
            return parts[1].lower().strip(), quantity
        except ValueError:
            pass

    # Check for trailing quantity like "milk x3" or "milk x 3"
    if " x" in item_str.lower():
        parts = item_str.lower().rsplit(" x", 1)
        if len(parts) == 2:
            try:
                quantity = int(parts[1].strip())
                return parts[0].strip(), quantity
            except ValueError:
                pass

    return item_str.lower().strip(), 1
