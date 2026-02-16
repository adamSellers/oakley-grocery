"""Tests for woolworths.py — product parsing and search helpers."""

import pytest


def test_parse_product_basic():
    from oakley_grocery.woolworths import _parse_product

    raw = {
        "Stockcode": 12345,
        "Name": "Pauls Full Cream Milk",
        "Brand": "Pauls",
        "Price": 4.50,
        "WasPrice": None,
        "IsOnSpecial": False,
        "CupPrice": 0.225,
        "CupString": "$0.225 per 100mL",
        "PackageSize": "2L",
        "IsAvailable": True,
        "MediumImageFile": "https://example.com/img.jpg",
        "Aisle": "Dairy",
        "Description": "Fresh full cream milk",
    }

    result = _parse_product(raw)
    assert result["stockcode"] == 12345
    assert result["name"] == "Pauls Full Cream Milk"
    assert result["brand"] == "Pauls"
    assert result["price"] == 4.50
    assert result["was_price"] is None
    assert result["on_special"] is False
    assert result["cup_price"] == 0.225
    assert result["package_size"] == "2L"
    assert result["available"] is True


def test_parse_product_on_special():
    from oakley_grocery.woolworths import _parse_product

    raw = {
        "Stockcode": 12345,
        "Name": "Pauls Milk",
        "Brand": "Pauls",
        "Price": 3.50,
        "WasPrice": 4.50,
        "IsOnSpecial": True,
        "PackageSize": "2L",
        "IsAvailable": True,
    }

    result = _parse_product(raw)
    assert result["on_special"] is True
    assert result["price"] == 3.50
    assert result["was_price"] == 4.50


def test_parse_product_unavailable():
    from oakley_grocery.woolworths import _parse_product

    raw = {
        "Stockcode": 99999,
        "Name": "Out Of Stock Item",
        "IsAvailable": False,
    }

    result = _parse_product(raw)
    assert result["available"] is False
    assert result["stockcode"] == 99999


def test_parse_product_missing_fields():
    from oakley_grocery.woolworths import _parse_product

    raw = {"Stockcode": 11111}
    result = _parse_product(raw)
    assert result["stockcode"] == 11111
    assert result["name"] == ""
    assert result["brand"] == ""
    assert result["price"] is None
    assert result["available"] is True


def test_parse_product_instore_price():
    from oakley_grocery.woolworths import _parse_product

    raw = {
        "Stockcode": 22222,
        "Name": "Instore Item",
        "InstorePrice": 5.99,
        "Price": None,
    }

    result = _parse_product(raw)
    assert result["price"] == 5.99


def test_parse_product_display_name_fallback():
    from oakley_grocery.woolworths import _parse_product

    raw = {
        "Stockcode": 33333,
        "DisplayName": "Display Name",
    }

    result = _parse_product(raw)
    assert result["name"] == "Display Name"


def test_parse_product_instore_special():
    from oakley_grocery.woolworths import _parse_product

    raw = {
        "Stockcode": 44444,
        "Name": "Instore Special",
        "Price": 2.99,
        "WasPrice": 3.99,
        "IsOnSpecial": False,
        "IsInStoreSpecial": True,
    }

    result = _parse_product(raw)
    assert result["on_special"] is True
    assert result["was_price"] == 3.99
