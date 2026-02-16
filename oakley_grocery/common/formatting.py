from __future__ import annotations

from datetime import datetime
from typing import Optional

import pytz

from .config import Config

_tz = pytz.timezone(Config.timezone)


def now_aest() -> datetime:
    return datetime.now(_tz)


def format_datetime_aest(dt: Optional[datetime] = None, fmt: str = "%d %b %Y %H:%M AEST") -> str:
    if dt is None:
        dt = now_aest()
    elif dt.tzinfo is None:
        dt = _tz.localize(dt)
    return dt.strftime(fmt)


def format_section_header(title: str) -> str:
    return f"**{title}**"


def format_list_item(text: str, indent: int = 0) -> str:
    prefix = "  " * indent
    return f"{prefix}- {text}"


def format_price(price: Optional[float]) -> str:
    """Format a price like '$4.50'."""
    if price is None:
        return "N/A"
    return f"${price:.2f}"


def format_price_change(current: float, previous: float) -> str:
    """Format price change like '$4.50 (was $5.00, -10%)'."""
    diff = current - previous
    pct = (diff / previous) * 100 if previous else 0
    direction = "+" if diff > 0 else ""
    return f"{format_price(current)} (was {format_price(previous)}, {direction}{pct:.0f}%)"


def format_shopping_list(items: list[dict], show_prices: bool = True) -> str:
    """Format a shopping list for display."""
    lines = []
    total = 0.0
    for item in items:
        qty = item.get("quantity", 1)
        name = item.get("generic_name", "?")
        product = item.get("product_name", "")
        price = item.get("price")
        checked = item.get("checked", 0)

        check = "[x]" if checked else "[ ]"

        if product and product != name:
            display = f"{check} {qty}x {name} -> {product}"
        else:
            display = f"{check} {qty}x {name}"

        if show_prices and price is not None:
            line_total = price * qty
            total += line_total
            display += f" ({format_price(price)} ea, {format_price(line_total)})"

        if item.get("on_special"):
            display += " *SPECIAL*"

        lines.append(display)

    if show_prices and total > 0:
        lines.append("")
        lines.append(f"Estimated total: {format_price(total)}")

    return "\n".join(lines)


def format_danmurphys_price(product: dict) -> str:
    """Format Dan Murphy's multi-tier pricing.

    Shows single price, plus any-six and case prices if different.
    Example: '$19.99 ea | $17.99 any six | $107.70 case'
    """
    parts = []
    single = product.get("price")
    six = product.get("six_price")
    case = product.get("case_price")

    if single is not None:
        parts.append(f"{format_price(single)} ea")
    if six is not None and six != single:
        parts.append(f"{format_price(six)} any six")
    if case is not None:
        parts.append(f"{format_price(case)} case")

    return " | ".join(parts) if parts else "N/A"


def truncate_for_telegram(text: str, max_length: int = Config.telegram_max_length) -> str:
    if len(text) <= max_length:
        return text
    truncated = text[: max_length - 30]
    last_newline = truncated.rfind("\n")
    if last_newline > max_length // 2:
        truncated = truncated[:last_newline]
    return truncated + "\n\n... (truncated)"
