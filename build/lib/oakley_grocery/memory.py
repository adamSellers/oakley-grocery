"""Weekly shop intelligence — usual items, suggestions, frequency, spending."""

from __future__ import annotations

from typing import Optional

from oakley_grocery import db
from oakley_grocery.common.config import Config


def build_usual(min_frequency: int = 0, lookback_orders: int = 0,
                exclude: Optional[list[str]] = None) -> list[dict]:
    """Build "the usual" shopping list from purchase history.

    Returns items appearing in min_frequency+ of the last lookback_orders.

    Returns:
        list of {"generic_name": str, "frequency": int, "product_name": str,
                 "brand": str, "stockcode": int, "avg_price": float}
    """
    if not min_frequency:
        min_frequency = Config.default_usual_min_frequency
    if not lookback_orders:
        lookback_orders = Config.default_usual_lookback_orders

    items = db.get_frequent_items(
        min_orders=min_frequency,
        lookback=lookback_orders,
    )

    if exclude:
        exclude_lower = {e.lower().strip() for e in exclude}
        items = [i for i in items if i["generic_name"] not in exclude_lower]

    return items


def suggest_additions(list_id: int) -> list[dict]:
    """Suggest items from "the usual" that aren't in the current list.

    Returns:
        list of usual items not present in the given list
    """
    list_items = db.get_list_items(list_id)
    current_items = {item["generic_name"] for item in list_items}

    usual = build_usual()
    suggestions = [
        item for item in usual
        if item["generic_name"] not in current_items
    ]

    return suggestions


def get_purchase_frequency(generic_name: str) -> dict:
    """Get purchase statistics for a specific item.

    Returns:
        {"generic_name": str, "total_purchases": int, "total_quantity": int,
         "avg_price": float, "last_price": float, "preference": dict|None}
    """
    conn = db._get_conn()

    # Count orders containing this item
    row = conn.execute(
        """SELECT COUNT(DISTINCT order_id) as order_count,
                  SUM(quantity) as total_qty,
                  AVG(price) as avg_price,
                  MAX(price) as max_price,
                  MIN(price) as min_price
           FROM order_items
           WHERE generic_name = ?""",
        (generic_name.lower().strip(),),
    ).fetchone()

    stats = dict(row) if row else {
        "order_count": 0, "total_qty": 0, "avg_price": None,
        "max_price": None, "min_price": None,
    }

    # Get preference
    pref = db.get_preference(generic_name)

    return {
        "generic_name": generic_name.lower().strip(),
        "total_purchases": stats["order_count"] or 0,
        "total_quantity": stats["total_qty"] or 0,
        "avg_price": stats["avg_price"],
        "max_price": stats["max_price"],
        "min_price": stats["min_price"],
        "preference": pref,
    }


def get_spending_summary(period_days: int = 30) -> dict:
    """Get spending summary for a time period.

    Returns:
        {"period_days": int, "order_count": int, "total_spent": float,
         "avg_order": float, "top_items": list[dict]}
    """
    stats = db.get_spending_stats(days=period_days)

    # Get top items by spend in period
    conn = db._get_conn()
    rows = conn.execute(
        """SELECT oi.generic_name,
                  SUM(oi.quantity) as total_qty,
                  SUM(oi.price * oi.quantity) as total_spend,
                  COUNT(DISTINCT oi.order_id) as appearances
           FROM order_items oi
           JOIN orders o ON oi.order_id = o.id
           WHERE o.created_at >= datetime('now', ? || ' days')
             AND oi.price IS NOT NULL
           GROUP BY oi.generic_name
           ORDER BY total_spend DESC
           LIMIT 10""",
        (f"-{period_days}",),
    ).fetchall()

    top_items = [dict(r) for r in rows]

    return {
        "period_days": period_days,
        "order_count": stats.get("order_count", 0),
        "total_spent": stats.get("total_spent", 0),
        "avg_order": stats.get("avg_order", 0),
        "max_order": stats.get("max_order", 0),
        "min_order": stats.get("min_order", 0),
        "top_items": top_items,
    }
