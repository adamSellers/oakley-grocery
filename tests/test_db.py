"""Tests for db.py — SQLite CRUD operations."""

import os
import sqlite3
import tempfile
import pytest


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    monkeypatch.setenv("OAKLEY_GROCERY_DATA_DIR", str(tmp_path))
    # Force reimport to pick up new data dir
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
    db_mod._conn = None  # Reset connection
    yield tmp_path
    db_mod._conn = None


# ─── Preferences ─────────────────────────────────────────────────────────────

def test_save_preference_new():
    from oakley_grocery import db
    row_id = db.save_preference("milk", 12345, "Pauls Full Cream 2L", "Pauls", "2L", 4.50)
    assert row_id > 0

    pref = db.get_preference("milk")
    assert pref is not None
    assert pref["stockcode"] == 12345
    assert pref["product_name"] == "Pauls Full Cream 2L"
    assert pref["brand"] == "Pauls"
    assert pref["purchase_count"] == 1
    assert pref["last_price"] == 4.50


def test_save_preference_updates():
    from oakley_grocery import db
    db.save_preference("milk", 12345, "Pauls Full Cream 2L", "Pauls", "2L", 4.50)
    db.save_preference("milk", 12345, "Pauls Full Cream 2L", "Pauls", "2L", 4.75)

    pref = db.get_preference("milk")
    assert pref["purchase_count"] == 2
    assert pref["last_price"] == 4.75


def test_save_preference_case_insensitive():
    from oakley_grocery import db
    db.save_preference("Milk", 12345, "Pauls Full Cream 2L")

    assert db.get_preference("milk") is not None
    assert db.get_preference("MILK") is not None
    assert db.get_preference("  milk  ") is not None


def test_delete_preference():
    from oakley_grocery import db
    db.save_preference("milk", 12345, "Pauls Full Cream 2L")
    assert db.delete_preference("milk") is True
    assert db.get_preference("milk") is None
    assert db.delete_preference("milk") is False


def test_search_preferences():
    from oakley_grocery import db
    db.save_preference("full cream milk", 12345, "Pauls Full Cream 2L")
    db.save_preference("skim milk", 12346, "Pauls Skim Milk 2L")
    db.save_preference("bread", 12347, "Tip Top White")

    results = db.search_preferences("milk")
    assert len(results) == 2


def test_get_all_preferences():
    from oakley_grocery import db
    db.save_preference("milk", 12345, "Pauls Full Cream 2L")
    db.save_preference("bread", 12346, "Tip Top White")

    prefs = db.get_all_preferences()
    assert len(prefs) == 2


def test_count_preferences():
    from oakley_grocery import db
    assert db.count_preferences() == 0
    db.save_preference("milk", 12345, "Pauls Full Cream 2L")
    assert db.count_preferences() == 1


# ─── Lists ───────────────────────────────────────────────────────────────────

def test_create_list():
    from oakley_grocery import db
    list_id = db.create_list("Weekly Shop")
    assert list_id > 0

    lst = db.get_list(list_id)
    assert lst["name"] == "Weekly Shop"
    assert lst["status"] == "active"


def test_get_lists():
    from oakley_grocery import db
    db.create_list("List 1")
    db.create_list("List 2")

    all_lists = db.get_lists()
    assert len(all_lists) == 2


def test_get_lists_by_status():
    from oakley_grocery import db
    id1 = db.create_list("Active")
    id2 = db.create_list("Purchased")
    db.update_list_status(id2, "purchased")

    active = db.get_lists("active")
    assert len(active) == 1
    assert active[0]["name"] == "Active"


def test_update_list_status():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    db.update_list_status(list_id, "purchased", total_estimate=85.50)

    lst = db.get_list(list_id)
    assert lst["status"] == "purchased"
    assert lst["total_estimate"] == 85.50


def test_delete_list():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    assert db.delete_list(list_id) is True
    assert db.get_list(list_id) is None


def test_count_lists():
    from oakley_grocery import db
    assert db.count_lists() == 0
    db.create_list("Test")
    assert db.count_lists() == 1
    assert db.count_lists("active") == 1


# ─── List Items ──────────────────────────────────────────────────────────────

def test_add_list_item():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    item_id = db.add_list_item(list_id, "milk", 2)
    assert item_id > 0

    items = db.get_list_items(list_id)
    assert len(items) == 1
    assert items[0]["generic_name"] == "milk"
    assert items[0]["quantity"] == 2


def test_add_list_item_merge_duplicates():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    db.add_list_item(list_id, "milk", 1)
    db.add_list_item(list_id, "milk", 2)

    items = db.get_list_items(list_id)
    assert len(items) == 1
    assert items[0]["quantity"] == 3


def test_add_list_item_case_insensitive():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    db.add_list_item(list_id, "Milk", 1)
    db.add_list_item(list_id, "MILK", 2)

    items = db.get_list_items(list_id)
    assert len(items) == 1
    assert items[0]["quantity"] == 3


def test_update_list_item():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    item_id = db.add_list_item(list_id, "milk")

    db.update_list_item(item_id, stockcode=12345, product_name="Pauls 2L", price=4.50, resolved=1)

    items = db.get_list_items(list_id)
    assert items[0]["stockcode"] == 12345
    assert items[0]["product_name"] == "Pauls 2L"
    assert items[0]["price"] == 4.50
    assert items[0]["resolved"] == 1


def test_remove_list_item():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    db.add_list_item(list_id, "milk")
    db.add_list_item(list_id, "bread")

    assert db.remove_list_item(list_id, "milk") is True
    items = db.get_list_items(list_id)
    assert len(items) == 1
    assert items[0]["generic_name"] == "bread"


def test_remove_list_item_not_found():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    assert db.remove_list_item(list_id, "nonexistent") is False


# ─── Orders ──────────────────────────────────────────────────────────────────

def test_create_order():
    from oakley_grocery import db
    list_id = db.create_list("Test")
    order_id = db.create_order(list_id, 85.0, 92.30, 10)
    assert order_id > 0

    order = db.get_order(order_id)
    assert order["total_paid"] == 92.30
    assert order["item_count"] == 10


def test_add_order_item():
    from oakley_grocery import db
    order_id = db.create_order(None, None, 50.0, 3)
    item_id = db.add_order_item(order_id, "milk", 12345, "Pauls 2L", "Pauls", 1, 4.50)
    assert item_id > 0

    items = db.get_order_items(order_id)
    assert len(items) == 1
    assert items[0]["generic_name"] == "milk"


def test_get_orders():
    from oakley_grocery import db
    db.create_order(None, None, 50.0, 3)
    db.create_order(None, None, 75.0, 5)

    orders = db.get_orders()
    assert len(orders) == 2


def test_count_orders():
    from oakley_grocery import db
    assert db.count_orders() == 0
    db.create_order(None, None, 50.0, 3)
    assert db.count_orders() == 1


# ─── Price History ───────────────────────────────────────────────────────────

def test_record_price():
    from oakley_grocery import db
    row_id = db.record_price(12345, "Pauls 2L", 4.50)
    assert row_id > 0


def test_get_price_history():
    from oakley_grocery import db
    db.record_price(12345, "Pauls 2L", 4.50)
    db.record_price(12345, "Pauls 2L", 4.75, on_special=True)
    db.record_price(12346, "Tip Top White", 3.50)

    history = db.get_price_history(stockcode=12345)
    assert len(history) == 2

    all_history = db.get_price_history()
    assert len(all_history) == 3


# ─── Frequent Items ─────────────────────────────────────────────────────────

def test_get_frequent_items():
    from oakley_grocery import db

    # Create 4 orders, each with milk
    for i in range(4):
        order_id = db.create_order(None, None, 50.0, 2)
        db.add_order_item(order_id, "milk", 12345, "Pauls 2L", "Pauls", 1, 4.50)
        if i < 2:
            db.add_order_item(order_id, "bread", 12346, "Tip Top", "Tip Top", 1, 3.50)

    # Milk in 4/4 orders, bread in 2/4
    items = db.get_frequent_items(min_orders=3, lookback=10)
    assert len(items) == 1
    assert items[0]["generic_name"] == "milk"

    items = db.get_frequent_items(min_orders=2, lookback=10)
    assert len(items) == 2


# ─── Spending Stats ──────────────────────────────────────────────────────────

def test_get_spending_stats():
    from oakley_grocery import db
    db.create_order(None, None, 50.0, 3)
    db.create_order(None, None, 75.0, 5)

    stats = db.get_spending_stats(days=30)
    assert stats["order_count"] == 2
    assert stats["total_spent"] == 125.0
    assert stats["avg_order"] == 62.5
