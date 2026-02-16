"""Tests for danmurphys.py — product parsing and search helpers."""

import pytest

from oakley_grocery.danmurphys import _parse_product, _extract_detail


class TestExtractDetail:
    def test_exact_match(self):
        details = [
            {"Name": "varietal", "Value": "Shiraz"},
            {"Name": "webregionoforigin", "Value": "Barossa Valley"},
        ]
        assert _extract_detail(details, "varietal") == "Shiraz"
        assert _extract_detail(details, "webregionoforigin") == "Barossa Valley"

    def test_case_insensitive(self):
        details = [{"Name": "Varietal", "Value": "Pinot Noir"}]
        assert _extract_detail(details, "varietal") == "Pinot Noir"
        assert _extract_detail(details, "VARIETAL") == "Pinot Noir"

    def test_missing_key(self):
        details = [{"Name": "varietal", "Value": "Shiraz"}]
        assert _extract_detail(details, "missing") == ""

    def test_empty_list(self):
        assert _extract_detail([], "anything") == ""

    def test_none_list(self):
        assert _extract_detail(None, "anything") == ""

    def test_boolean_value_returns_empty(self):
        details = [{"Name": "webdsvflag", "Value": False}]
        assert _extract_detail(details, "webdsvflag") == ""

    def test_numeric_value_converted_to_string(self):
        details = [{"Name": "webtotalreviewcount", "Value": 335}]
        assert _extract_detail(details, "webtotalreviewcount") == "335"


class TestParseProduct:
    def test_full_product(self):
        raw = {
            "Stockcode": "144469",
            "Brand": "Pepperjack",
            "Title": "Pepperjack Barossa Shiraz",
            "VolumeSize": "750ML",
            "Price": {
                "singleprice": {"Value": 19.95, "IsMemberOffer": False},
                "inanysixprice": {"Value": 17.95},
                "caseprice": {"Value": 107.70},
            },
            "IsSpecial": False,
            "AmountSaved": 0.00,
            "ImageFile": "https://example.com/img.png",
            "AdditionalDetails": [
                {"Name": "varietal", "Value": "Shiraz"},
                {"Name": "webregionoforigin", "Value": "Barossa Valley"},
                {"Name": "webalcoholpercentage", "Value": "14.5%"},
                {"Name": "webaverageproductrating", "Value": "4.3672"},
                {"Name": "webtotalreviewcount", "Value": 335},
                {"Name": "webwinebody", "Value": "Full Bodied"},
                {"Name": "webmaincategory", "Value": "redwine"},
                {"Name": "webdescriptionshort", "Value": "Rich and round."},
            ],
        }

        result = _parse_product(raw)
        assert result["stockcode"] == "144469"
        assert result["name"] == "Pepperjack Barossa Shiraz"
        assert result["brand"] == "Pepperjack"
        assert result["volume"] == "750ML"
        assert result["price"] == 19.95
        assert result["six_price"] == 17.95
        assert result["case_price"] == 107.70
        assert result["on_special"] is False
        assert result["was_price"] is None
        assert result["varietal"] == "Shiraz"
        assert result["region"] == "Barossa Valley"
        assert result["alcohol_pct"] == "14.5%"
        assert result["rating"] == "4.3672"
        assert result["review_count"] == "335"
        assert result["wine_body"] == "Full Bodied"
        assert result["category"] == "redwine"
        assert result["description"] == "Rich and round."
        assert result["image_url"] == "https://example.com/img.png"
        assert result["store"] == "dan-murphys"

    def test_on_special(self):
        raw = {
            "Stockcode": "888002",
            "Title": "Sale Wine",
            "Brand": "TestBrand",
            "Price": {
                "singleprice": {
                    "Value": 15.99,
                    "BeforePromotion": 19.99,
                },
            },
            "IsSpecial": True,
            "AmountSaved": 4.00,
        }

        result = _parse_product(raw)
        assert result["on_special"] is True
        assert result["price"] == 15.99
        assert result["was_price"] == 19.99
        assert result["amount_saved"] == 4.00

    def test_not_special_hides_was_price(self):
        raw = {
            "Stockcode": "888003",
            "Title": "Regular Wine",
            "Price": {
                "singleprice": {
                    "Value": 29.99,
                    "BeforePromotion": 35.00,
                },
            },
            "IsSpecial": False,
        }

        result = _parse_product(raw)
        assert result["on_special"] is False
        assert result["was_price"] is None

    def test_member_offer(self):
        raw = {
            "Stockcode": "888004",
            "Title": "Member Beer",
            "Price": {
                "singleprice": {
                    "Value": 49.99,
                    "IsMemberOffer": True,
                },
            },
        }

        result = _parse_product(raw)
        assert result["is_member_offer"] is True

    def test_missing_fields(self):
        raw = {"Stockcode": "888005"}
        result = _parse_product(raw)
        assert result["stockcode"] == "888005"
        assert result["name"] == ""
        assert result["brand"] == ""
        assert result["volume"] == ""
        assert result["price"] is None
        assert result["six_price"] is None
        assert result["case_price"] is None
        assert result["varietal"] == ""
        assert result["region"] == ""
        assert result["store"] == "dan-murphys"

    def test_flat_price_fallback(self):
        raw = {
            "Stockcode": "888006",
            "Title": "Simple Product",
            "Price": 29.99,
        }

        result = _parse_product(raw)
        assert result["price"] == 29.99
        assert result["six_price"] is None
        assert result["case_price"] is None

    def test_empty_price_object(self):
        raw = {
            "Stockcode": "888007",
            "Title": "No Price",
            "Price": {},
        }

        result = _parse_product(raw)
        assert result["price"] is None

    def test_null_price(self):
        raw = {
            "Stockcode": "888008",
            "Title": "Null Price",
            "Price": None,
        }

        result = _parse_product(raw)
        assert result["price"] is None

    def test_name_fallback_to_name_field(self):
        raw = {
            "Stockcode": "888009",
            "Name": "Fallback Name",
        }

        result = _parse_product(raw)
        assert result["name"] == "Fallback Name"

    def test_no_additional_details(self):
        raw = {
            "Stockcode": "888010",
            "Title": "No Details",
            "AdditionalDetails": None,
        }

        result = _parse_product(raw)
        assert result["varietal"] == ""
        assert result["region"] == ""
        assert result["alcohol_pct"] == ""
