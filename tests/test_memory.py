"""Tests for memory.py — weekly shop intelligence."""

import pytest


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


def _create_orders_with_items(n_orders, items_per_order):
    """Helper: create n orders, each with the given items."""
    from oakley_grocery import db
    for i in range(n_orders):
        order_id = db.create_order(None, None, 50.0 + i, len(items_per_order))
        for generic, stockcode, product, brand, price in items_per_order:
            db.add_order_item(order_id, generic, stockcode, product, brand, 1, price)


# ─── Build Usual ─────────────────────────────────────────────────────────────

def test_build_usual_not_enough_orders():
    from oakley_grocery.memory import build_usual
    items = build_usual()
    assert items == []


def test_build_usual_returns_frequent_items():
    from oakley_grocery.memory import build_usual

    # Create 5 orders, each with milk. Bread only in 2.
    from oakley_grocery import db
    for i in range(5):
        order_id = db.create_order(None, None, 50.0, 2)
        db.add_order_item(order_id, "milk", 12345, "Pauls 2L", "Pauls", 1, 4.50)
        if i < 2:
            db.add_order_item(order_id, "bread", 12346, "Tip Top", "Tip Top", 1, 3.50)

    items = build_usual(min_frequency=3, lookback_orders=10)
    assert len(items) == 1
    assert items[0]["generic_name"] == "milk"


def test_build_usual_with_exclude():
    from oakley_grocery.memory import build_usual
    from oakley_grocery import db

    for i in range(4):
        order_id = db.create_order(None, None, 50.0, 2)
        db.add_order_item(order_id, "milk", 12345, "Pauls 2L", "Pauls", 1, 4.50)
        db.add_order_item(order_id, "bread", 12346, "Tip Top", "Tip Top", 1, 3.50)

    items = build_usual(min_frequency=3, lookback_orders=10, exclude=["bread"])
    names = [i["generic_name"] for i in items]
    assert "bread" not in names
    assert "milk" in names


# ─── Suggest Additions ───────────────────────────────────────────────────────

def test_suggest_additions():
    from oakley_grocery.memory import suggest_additions
    from oakley_grocery import db

    # Create history with milk and bread frequent
    for i in range(4):
        order_id = db.create_order(None, None, 50.0, 2)
        db.add_order_item(order_id, "milk", 12345, "Pauls 2L", "Pauls", 1, 4.50)
        db.add_order_item(order_id, "bread", 12346, "Tip Top", "Tip Top", 1, 3.50)

    # Create a list with only milk
    list_id = db.create_list("Test")
    db.add_list_item(list_id, "milk")

    suggestions = suggest_additions(list_id)
    names = [s["generic_name"] for s in suggestions]
    assert "bread" in names
    assert "milk" not in names


# ─── Purchase Frequency ─────────────────────────────────────────────────────

def test_get_purchase_frequency():
    from oakley_grocery.memory import get_purchase_frequency
    from oakley_grocery import db

    for i in range(3):
        order_id = db.create_order(None, None, 50.0, 1)
        db.add_order_item(order_id, "milk", 12345, "Pauls 2L", "Pauls", 1, 4.50)

    freq = get_purchase_frequency("milk")
    assert freq["total_purchases"] == 3
    assert freq["total_quantity"] == 3
    assert freq["avg_price"] == 4.50


def test_get_purchase_frequency_no_history():
    from oakley_grocery.memory import get_purchase_frequency
    freq = get_purchase_frequency("nonexistent")
    assert freq["total_purchases"] == 0


# ─── Spending Summary ───────────────────────────────────────────────────────

def test_get_spending_summary():
    from oakley_grocery.memory import get_spending_summary
    from oakley_grocery import db

    order1 = db.create_order(None, None, 50.0, 2)
    db.add_order_item(order1, "milk", 12345, "Pauls 2L", "Pauls", 1, 4.50)
    db.add_order_item(order1, "bread", 12346, "Tip Top", "Tip Top", 1, 3.50)

    order2 = db.create_order(None, None, 75.0, 1)
    db.add_order_item(order2, "milk", 12345, "Pauls 2L", "Pauls", 2, 4.50)

    summary = get_spending_summary(period_days=30)
    assert summary["order_count"] == 2
    assert summary["total_spent"] == 125.0
    assert len(summary["top_items"]) >= 1


def test_get_spending_summary_empty():
    from oakley_grocery.memory import get_spending_summary
    summary = get_spending_summary(period_days=30)
    assert summary["order_count"] == 0
    assert summary["total_spent"] == 0
