"""Tests for resolver.py — product resolution pipeline."""

import pytest
from unittest.mock import patch, MagicMock


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


# ─── Tokenization & Scoring ─────────────────────────────────────────────────

def test_tokenize():
    from oakley_grocery.resolver import _tokenize
    assert _tokenize("full cream milk") == {"full", "cream", "milk"}
    assert _tokenize("") == set()
    assert _tokenize("MILK") == {"milk"}


def test_jaccard_identical():
    from oakley_grocery.resolver import _jaccard
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint():
    from oakley_grocery.resolver import _jaccard
    assert _jaccard({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_partial():
    from oakley_grocery.resolver import _jaccard
    result = _jaccard({"a", "b", "c"}, {"a", "b", "d"})
    assert abs(result - 0.5) < 0.01  # 2/4


def test_jaccard_empty():
    from oakley_grocery.resolver import _jaccard
    assert _jaccard(set(), {"a"}) == 0.0
    assert _jaccard(set(), set()) == 0.0


def test_calculate_relevance_name_match():
    from oakley_grocery.resolver import _calculate_relevance
    product = {"name": "Full Cream Milk 2L", "available": True}
    score = _calculate_relevance(product, "full cream milk")
    assert score > 0.2  # Name overlap should contribute


def test_calculate_relevance_brand_match():
    from oakley_grocery.resolver import _calculate_relevance
    product = {"name": "Full Cream Milk", "brand": "Pauls", "available": True}
    score_with_brand = _calculate_relevance(product, "milk", prefer_brand="Pauls")
    score_without_brand = _calculate_relevance(product, "milk")
    assert score_with_brand > score_without_brand


def test_calculate_relevance_size_match():
    from oakley_grocery.resolver import _calculate_relevance
    product = {"name": "Milk", "package_size": "2L", "available": True}
    score_with_size = _calculate_relevance(product, "milk", prefer_size="2L")
    score_without_size = _calculate_relevance(product, "milk")
    assert score_with_size > score_without_size


def test_calculate_relevance_on_special():
    from oakley_grocery.resolver import _calculate_relevance
    product_special = {"name": "Milk", "on_special": True, "available": True}
    product_normal = {"name": "Milk", "on_special": False, "available": True}
    score_special = _calculate_relevance(product_special, "milk")
    score_normal = _calculate_relevance(product_normal, "milk")
    assert score_special > score_normal


def test_calculate_relevance_unavailable_penalty():
    from oakley_grocery.resolver import _calculate_relevance
    product_available = {"name": "Milk", "available": True}
    product_unavailable = {"name": "Milk", "available": False}
    score_available = _calculate_relevance(product_available, "milk")
    score_unavailable = _calculate_relevance(product_unavailable, "milk")
    assert score_available > score_unavailable


# ─── Preference Resolution ──────────────────────────────────────────────────

def test_resolve_from_preference():
    from oakley_grocery import db
    from oakley_grocery.resolver import resolve_item

    db.save_preference("milk", 12345, "Pauls Full Cream 2L", "Pauls", "2L", 4.50)

    result = resolve_item("milk")
    assert result["resolved"] is True
    assert result["source"] == "preference"
    assert result["product"]["stockcode"] == 12345


def test_resolve_from_preference_case_insensitive():
    from oakley_grocery import db
    from oakley_grocery.resolver import resolve_item

    db.save_preference("milk", 12345, "Pauls Full Cream 2L")

    result = resolve_item("MILK")
    assert result["resolved"] is True
    assert result["source"] == "preference"


def test_resolve_fuzzy_preference():
    from oakley_grocery import db
    from oakley_grocery.resolver import resolve_item

    db.save_preference("full cream milk", 12345, "Pauls Full Cream 2L")

    # "cream milk" should fuzzy-match "full cream milk"
    result = resolve_item("cream milk")
    assert result["resolved"] is True
    assert result["source"] == "preference"


# ─── Search Resolution ──────────────────────────────────────────────────────

@patch("oakley_grocery.resolver.woolworths.search_products")
def test_resolve_from_search_auto(mock_search):
    from oakley_grocery.resolver import resolve_item

    mock_search.return_value = [
        {"stockcode": 100, "name": "Full Cream Milk", "brand": "Pauls", "price": 4.50, "available": True, "on_special": True, "package_size": "2L"},
        {"stockcode": 101, "name": "Chocolate Flavoured Drink 600mL", "brand": "Oak", "price": 3.00, "available": True, "on_special": False, "package_size": "600mL"},
    ]

    result = resolve_item("full cream milk")
    assert result["resolved"] is True
    assert result["source"] == "search"
    assert result["product"]["stockcode"] == 100


@patch("oakley_grocery.resolver.woolworths.search_products")
def test_resolve_from_search_disambiguation(mock_search):
    from oakley_grocery.resolver import resolve_item

    # Two very similar products — should need disambiguation
    mock_search.return_value = [
        {"stockcode": 100, "name": "Milk 2L", "brand": "Brand A", "price": 4.50, "available": True, "on_special": False, "package_size": "2L"},
        {"stockcode": 101, "name": "Milk 2L", "brand": "Brand B", "price": 4.00, "available": True, "on_special": False, "package_size": "2L"},
    ]

    result = resolve_item("milk 2l")
    # Both should be in candidates
    assert len(result["candidates"]) >= 2


@patch("oakley_grocery.resolver.woolworths.search_products")
def test_resolve_search_failure(mock_search):
    from oakley_grocery.resolver import resolve_item

    mock_search.side_effect = RuntimeError("API down")

    result = resolve_item("milk")
    assert result["resolved"] is False
    assert result["source"] == "unresolved"


@patch("oakley_grocery.resolver.woolworths.search_products")
def test_resolve_no_results(mock_search):
    from oakley_grocery.resolver import resolve_item

    mock_search.return_value = []

    result = resolve_item("nonexistent product")
    assert result["resolved"] is False
    assert result["candidates"] == []


# ─── Learn Preference ───────────────────────────────────────────────────────

def test_learn_preference():
    from oakley_grocery.resolver import learn_preference
    from oakley_grocery import db

    pref_id = learn_preference("milk", 12345, "Pauls Full Cream 2L", "Pauls", "2L", 4.50)
    assert pref_id > 0

    pref = db.get_preference("milk")
    assert pref["stockcode"] == 12345


# ─── Batch Resolution ───────────────────────────────────────────────────────

def test_resolve_list():
    from oakley_grocery import db
    from oakley_grocery.resolver import resolve_list

    db.save_preference("milk", 12345, "Pauls 2L")
    db.save_preference("bread", 12346, "Tip Top White")

    results = resolve_list([
        {"generic_name": "milk"},
        {"generic_name": "bread"},
    ])

    assert len(results) == 2
    assert all(r["resolved"] for r in results)
