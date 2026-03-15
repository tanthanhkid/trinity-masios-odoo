"""Unit tests for formatter helper functions: _safe_json, _money, _pct, _val, _dq."""
import json
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from formatter import _safe_json, _money, _pct, _val, _dq


class TestSafeJson:
    def test_valid_json_string(self):
        assert _safe_json('{"a": 1}') == {"a": 1}

    def test_valid_json_array(self):
        assert _safe_json('[1, 2]') == [1, 2]

    def test_wrapped_result_string(self):
        inner = json.dumps({"key": "val"})
        wrapped = json.dumps({"result": inner})
        assert _safe_json(wrapped) == {"key": "val"}

    def test_wrapped_result_non_json(self):
        wrapped = json.dumps({"result": "plain text"})
        result = _safe_json(wrapped)
        assert result == {"result": "plain text"}

    def test_invalid_json(self):
        assert _safe_json("not json") == {}

    def test_empty_string(self):
        assert _safe_json("") == {}

    def test_none_input(self):
        assert _safe_json(None) == {}

    def test_already_parsed_dict(self):
        # _safe_json receives str, but should handle gracefully
        assert _safe_json('{"x": 1}') == {"x": 1}


class TestMoney:
    def test_billions(self):
        assert _money(1_500_000_000) == "1.5 tỷ"

    def test_exact_billion(self):
        assert _money(1_000_000_000) == "1.0 tỷ"

    def test_millions(self):
        assert _money(25_500_000) == "25.5 triệu"

    def test_exact_million(self):
        assert _money(1_000_000) == "1.0 triệu"

    def test_thousands(self):
        assert _money(500_000) == "500K"

    def test_exact_thousand(self):
        assert _money(1_000) == "1K"

    def test_small_number(self):
        assert _money(999) == "999"

    def test_zero(self):
        assert _money(0) == "0"

    def test_none(self):
        assert _money(None) == "0"

    def test_string_number(self):
        assert _money("5000000") == "5.0 triệu"

    def test_invalid_string(self):
        assert _money("abc") == "0"

    def test_negative(self):
        # Negative numbers: abs < thresholds, falls through to comma format
        result = _money(-5_000_000)
        assert result == "-5,000,000"


class TestPct:
    def test_normal(self):
        assert _pct(85.5) == "85.5%"

    def test_zero(self):
        assert _pct(0) == "0.0%"

    def test_string_number(self):
        assert _pct("42.3") == "42.3%"

    def test_invalid(self):
        assert _pct("abc") == "abc"

    def test_none(self):
        assert _pct(None) == "None"


class TestVal:
    def test_first_key_found(self):
        assert _val({"a": 1, "b": 2}, "a", "b") == 1

    def test_second_key_found(self):
        assert _val({"b": 2}, "a", "b") == 2

    def test_no_key_found(self):
        assert _val({"c": 3}, "a", "b") is None

    def test_default_value(self):
        assert _val({}, "a", default=42) == 42

    def test_none_dict(self):
        assert _val(None, "a", default="x") == "x"

    def test_empty_dict(self):
        assert _val({}, "a") is None


class TestDq:
    def test_ok_quality(self):
        lines = []
        _dq(lines, {"data_quality": "ok"})
        assert lines == []

    def test_issue_quality(self):
        lines = []
        _dq(lines, {"data_quality": "warning", "data_issues": ["Missing field X"]})
        assert any("DATA ISSUE" in l for l in lines)
        assert any("Missing field X" in l for l in lines)

    def test_non_dict_input(self):
        lines = []
        _dq(lines, "not a dict")
        assert lines == []

    def test_no_issues_list(self):
        lines = []
        _dq(lines, {"data_quality": "warning", "data_issues": []})
        assert lines == []
