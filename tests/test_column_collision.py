"""Tests for column name collisions in flattened output."""

import io
import json

import pytest

from json_to_multicsv.converter import ConvertError, json_to_multicsv
from json_to_multicsv.parser import build_handlers


def _convert(data, path_specs, table_name=None):
    """Run the converter on in-memory data and return the tables dict."""
    fileobj = io.StringIO(json.dumps(data))
    handlers = build_handlers(path_specs)
    return json_to_multicsv(fileobj, handlers, table_name)


class TestNoCollision:
    def test_nested_column_preserves_prefix(self):
        """Nested column flattening keeps the parent key as prefix."""
        data = {"a": {"name": "alice", "address": {"city": "NYC", "zip": "10001"}}}
        tables = _convert(data, ["/:table:item", "/*/address:column"])
        rows = tables[("item",)]
        assert len(rows) == 1
        row = rows[0]
        assert row["name"] == "alice"
        assert row["address.city"] == "NYC"
        assert row["address.zip"] == "10001"

    def test_data_columns_not_prefixed_with_table_name(self):
        """Data columns should not carry the table name as prefix."""
        data = {"x": {"foo": 1, "bar": 2}}
        tables = _convert(data, ["/:table:item"])
        rows = tables[("item",)]
        row = rows[0]
        assert "foo" in row
        assert "bar" in row
        assert "item.foo" not in row
        assert "item.bar" not in row


class TestCollision:
    def test_dotted_key_collides_with_nested_path(self):
        """A JSON key containing '.' collides with a flattened nested path.

        If an object has both a key "a.b" and a nested object "a" with
        key "b", both produce the column name "a.b".  This should raise.
        """
        data = {
            "x": {
                "a.b": "from_dotted_key",
                "a": {"b": "from_nested"},
            }
        }
        with pytest.raises(ConvertError, match="Column name.*already exists"):
            _convert(data, ["/:table:item", "/*/a:column"])

    def test_dotted_key_without_nested_is_fine(self):
        """A dotted key with no matching nested path is unambiguous."""
        data = {"x": {"a.b": 42, "c": 7}}
        tables = _convert(data, ["/:table:item"])
        rows = tables[("item",)]
        row = rows[0]
        assert row["a.b"] == 42
        assert row["c"] == 7
