"""Tests for lists.py — shopping list engine."""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    import oakley_grocery.common.config as cfg
    cfg.DATA_DIR = tmp_path
    cfg.CACHE_DIR = tmp_path / "cache"
    cfg.DB_PATH = tmp_path / "grocery.db"
    cfg.CONFIG_PATH = tmp_path / "config.json"
    cfg.Config.data_dir = cfg.DATA_DIR
    cfg.Config.cache_dir = cfg.CACHE_DIR
    cfg.Config.db_path = cfg.DB_PATH
    cfg.Config.config_path = cfg.CONFIG_PATH

    import oakley_grocery.db as db_mod
    db_mod._conn = None
    yield tmp_path
    db_mod._conn = None


# ─── Parse Item String ──────────────────────────────────────────────────────

def test_parse_item_string_simple():
    from oakley_grocery.lists import _parse_item_string
    assert _parse_item_string("milk") == ("milk", 1)


def test_parse_item_string_with_quantity():
    from oakley_grocery.lists import _parse_item_string
    assert _parse_item_string("2 milk") == ("milk", 2)


def test_parse_item_string_trailing_quantity():
    from oakley_grocery.lists import _parse_item_string
    assert _parse_item_string("milk x3") == ("milk", 3)
    assert _parse_item_string("milk x 3") == ("milk", 3)


def test_parse_item_string_no_quantity_word():
    from oakley_grocery.lists import _parse_item_string
    assert _parse_item_string("full cream milk") == ("full cream milk", 1)


def test_parse_item_string_case_insensitive():
    from oakley_grocery.lists import _parse_item_string
    name, qty = _parse_item_string("MILK")
    assert name == "milk"


def test_parse_item_string_strips_whitespace():
    from oakley_grocery.lists import _parse_item_string
    name, qty = _parse_item_string("  milk  ")
    assert name == "milk"


# ─── Create List ─────────────────────────────────────────────────────────────

def test_create_list_empty():
    from oakley_grocery.lists import create_list
    result = create_list("Test")
    assert result["list_id"] > 0
    assert result["name"] == "Test"
    assert result["item_count"] == 0


def test_create_list_with_items():
    from oakley_grocery.lists import create_list
    result = create_list("Test", ["milk", "bread", "2 eggs"])
    assert result["item_count"] == 3


# ─── Add Items ───────────────────────────────────────────────────────────────

def test_add_items():
    from oakley_grocery.lists import create_list, add_items
    result = create_list("Test")
    add_result = add_items(result["list_id"], ["milk", "bread"])
    assert add_result["added"] == 2
    assert add_result["merged"] == 0


def test_add_items_merge_duplicates():
    from oakley_grocery.lists import create_list, add_items
    result = create_list("Test", ["milk"])
    add_result = add_items(result["list_id"], ["milk", "bread"])
    assert add_result["added"] == 1
    assert add_result["merged"] == 1


def test_add_items_list_not_found():
    from oakley_grocery.lists import add_items
    with pytest.raises(ValueError, match="not found"):
        add_items(999, ["milk"])


def test_add_items_inactive_list():
    from oakley_grocery.lists import create_list, add_items
    from oakley_grocery import db
    result = create_list("Test")
    db.update_list_status(result["list_id"], "purchased")
    with pytest.raises(ValueError, match="not active"):
        add_items(result["list_id"], ["milk"])


# ─── Remove Items ────────────────────────────────────────────────────────────

def test_remove_items():
    from oakley_grocery.lists import create_list, remove_items
    result = create_list("Test", ["milk", "bread", "eggs"])
    remove_result = remove_items(result["list_id"], ["milk", "eggs"])
    assert remove_result["removed"] == 2
    assert remove_result["not_found"] == []


def test_remove_items_not_found():
    from oakley_grocery.lists import create_list, remove_items
    result = create_list("Test", ["milk"])
    remove_result = remove_items(result["list_id"], ["bread"])
    assert remove_result["removed"] == 0
    assert "bread" in remove_result["not_found"]


# ─── Get List ────────────────────────────────────────────────────────────────

def test_get_list():
    from oakley_grocery.lists import create_list, get_list
    result = create_list("Test", ["milk", "bread"])
    data = get_list(result["list_id"])
    assert data["list"]["name"] == "Test"
    assert len(data["items"]) == 2
    assert data["stats"]["total"] == 2
    assert data["stats"]["resolved"] == 0


def test_get_list_not_found():
    from oakley_grocery.lists import get_list
    with pytest.raises(ValueError, match="not found"):
        get_list(999)


# ─── Mark Purchased ─────────────────────────────────────────────────────────

def test_mark_purchased():
    from oakley_grocery.lists import create_list, mark_purchased
    from oakley_grocery import db

    result = create_list("Test", ["milk", "bread"])
    list_id = result["list_id"]

    # Resolve items manually
    items = db.get_list_items(list_id)
    for item in items:
        db.update_list_item(item["id"], stockcode=12345, product_name="Product", price=4.50, resolved=1)

    purchase = mark_purchased(list_id, total_paid=92.30)
    assert purchase["order_id"] > 0
    assert purchase["items_logged"] == 2

    # Check list is marked purchased
    lst = db.get_list(list_id)
    assert lst["status"] == "purchased"

    # Check order exists
    order = db.get_order(purchase["order_id"])
    assert order["total_paid"] == 92.30


def test_mark_purchased_not_found():
    from oakley_grocery.lists import mark_purchased
    with pytest.raises(ValueError, match="not found"):
        mark_purchased(999)
