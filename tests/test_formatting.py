"""Tests for common/formatting.py"""

import pytest


def test_format_price_normal():
    from oakley_grocery.common.formatting import format_price
    assert format_price(4.50) == "$4.50"
    assert format_price(0.99) == "$0.99"
    assert format_price(123.0) == "$123.00"


def test_format_price_none():
    from oakley_grocery.common.formatting import format_price
    assert format_price(None) == "N/A"


def test_format_price_zero():
    from oakley_grocery.common.formatting import format_price
    assert format_price(0) == "$0.00"


def test_format_price_change_decrease():
    from oakley_grocery.common.formatting import format_price_change
    result = format_price_change(4.50, 5.00)
    assert "$4.50" in result
    assert "$5.00" in result
    assert "-10%" in result


def test_format_price_change_increase():
    from oakley_grocery.common.formatting import format_price_change
    result = format_price_change(5.50, 5.00)
    assert "+10%" in result


def test_format_section_header():
    from oakley_grocery.common.formatting import format_section_header
    assert format_section_header("Test") == "**Test**"


def test_format_list_item():
    from oakley_grocery.common.formatting import format_list_item
    assert format_list_item("milk") == "- milk"
    assert format_list_item("milk", indent=1) == "  - milk"
    assert format_list_item("milk", indent=2) == "    - milk"


def test_format_shopping_list_basic():
    from oakley_grocery.common.formatting import format_shopping_list
    items = [
        {"generic_name": "milk", "quantity": 1, "price": 4.50, "checked": 0},
        {"generic_name": "bread", "quantity": 2, "price": 3.00, "checked": 1},
    ]
    result = format_shopping_list(items)
    assert "[ ] 1x milk" in result
    assert "[x] 2x bread" in result
    assert "$4.50" in result
    assert "$6.00" in result  # 2 x $3.00
    assert "Estimated total: $10.50" in result


def test_format_shopping_list_with_product_name():
    from oakley_grocery.common.formatting import format_shopping_list
    items = [
        {"generic_name": "milk", "product_name": "Pauls Full Cream 2L", "quantity": 1, "price": 4.50, "checked": 0},
    ]
    result = format_shopping_list(items)
    assert "milk -> Pauls Full Cream 2L" in result


def test_format_shopping_list_on_special():
    from oakley_grocery.common.formatting import format_shopping_list
    items = [
        {"generic_name": "yoghurt", "quantity": 1, "price": 3.00, "checked": 0, "on_special": True},
    ]
    result = format_shopping_list(items)
    assert "*SPECIAL*" in result


def test_format_shopping_list_no_prices():
    from oakley_grocery.common.formatting import format_shopping_list
    items = [
        {"generic_name": "milk", "quantity": 1, "checked": 0},
    ]
    result = format_shopping_list(items, show_prices=True)
    assert "[ ] 1x milk" in result
    assert "Estimated total" not in result


def test_truncate_for_telegram_short():
    from oakley_grocery.common.formatting import truncate_for_telegram
    text = "Short text"
    assert truncate_for_telegram(text) == text


def test_truncate_for_telegram_long():
    from oakley_grocery.common.formatting import truncate_for_telegram
    text = "A" * 5000
    result = truncate_for_telegram(text, max_length=100)
    assert len(result) <= 100
    assert "truncated" in result


def test_now_aest():
    from oakley_grocery.common.formatting import now_aest
    dt = now_aest()
    assert dt.tzinfo is not None


def test_format_datetime_aest():
    from oakley_grocery.common.formatting import format_datetime_aest
    result = format_datetime_aest()
    assert "AEST" in result
