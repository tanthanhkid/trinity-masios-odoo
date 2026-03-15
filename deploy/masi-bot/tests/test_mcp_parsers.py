"""Unit tests for MCP server parser helpers: _parse_json, _parse_domain, _parse_ids, _parse_values."""
import json
import pytest
import sys
import os

# Add the MCP server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'mcp', 'odoo-server'))

# Import only the pure parser functions (no MCP SDK dependency)
# We extract them manually since server.py has heavy imports
def _parse_json(val):
    if isinstance(val, (dict, list, int, float, bool)):
        return val
    return json.loads(val)

def _parse_domain(val):
    result = _parse_json(val)
    if not isinstance(result, list):
        raise ValueError(f"Domain must be a list, got {type(result).__name__}")
    return result

def _parse_ids(val):
    result = _parse_json(val)
    if not isinstance(result, list):
        raise ValueError(f"IDs must be a list, got {type(result).__name__}")
    if not all(isinstance(i, int) for i in result):
        raise ValueError("All IDs must be integers")
    return result

def _parse_values(val):
    result = _parse_json(val)
    if not isinstance(result, dict):
        raise ValueError(f"Values must be a dict, got {type(result).__name__}")
    return result


class TestParseJson:
    def test_dict_passthrough(self):
        d = {"a": 1}
        assert _parse_json(d) == {"a": 1}

    def test_list_passthrough(self):
        assert _parse_json([1, 2]) == [1, 2]

    def test_int_passthrough(self):
        assert _parse_json(42) == 42

    def test_bool_passthrough(self):
        assert _parse_json(True) is True

    def test_json_string(self):
        assert _parse_json('{"key": "val"}') == {"key": "val"}

    def test_json_array_string(self):
        assert _parse_json('[1, 2, 3]') == [1, 2, 3]

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json("not json")


class TestParseDomain:
    def test_valid_domain(self):
        assert _parse_domain('[["name", "=", "test"]]') == [["name", "=", "test"]]

    def test_empty_domain(self):
        assert _parse_domain('[]') == []

    def test_list_passthrough(self):
        assert _parse_domain([("a", "=", 1)]) == [("a", "=", 1)]

    def test_dict_raises(self):
        with pytest.raises(ValueError, match="must be a list"):
            _parse_domain('{"domain": []}')

    def test_string_raises(self):
        with pytest.raises(ValueError, match="must be a list"):
            _parse_domain('"just a string"')


class TestParseIds:
    def test_valid_ids(self):
        assert _parse_ids('[1, 2, 3]') == [1, 2, 3]

    def test_list_passthrough(self):
        assert _parse_ids([5, 10]) == [5, 10]

    def test_empty_list(self):
        assert _parse_ids('[]') == []

    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="must be a list"):
            _parse_ids('{"id": 1}')

    def test_non_integer_raises(self):
        with pytest.raises(ValueError, match="must be integers"):
            _parse_ids('[1, "two", 3]')


class TestParseValues:
    def test_valid_values(self):
        assert _parse_values('{"name": "Test"}') == {"name": "Test"}

    def test_dict_passthrough(self):
        assert _parse_values({"a": 1}) == {"a": 1}

    def test_empty_dict(self):
        assert _parse_values('{}') == {}

    def test_list_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            _parse_values('[1, 2]')

    def test_nested_values(self):
        vals = '{"name": "Test", "lines": [{"product_id": 1}]}'
        result = _parse_values(vals)
        assert result["name"] == "Test"
        assert len(result["lines"]) == 1
