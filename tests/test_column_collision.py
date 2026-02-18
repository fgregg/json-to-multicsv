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


class TestCustomKeyName:
    def test_custom_key_name_in_output(self):
        """A table with key_name should use it instead of the default ._key."""
        data = {"x": {"foo": 1}, "y": {"foo": 2}}
        tables = _convert(data, ["/:table:item:rptId"])
        rows = tables[("item",)]
        assert len(rows) == 2
        assert "rptId" in rows[0]
        assert "item._key" not in rows[0]

    def test_default_key_name_when_omitted(self):
        """Without key_name, the default ._key column is used."""
        data = {"x": {"foo": 1}}
        tables = _convert(data, ["/:table:item"])
        rows = tables[("item",)]
        assert "item._key" in rows[0]

    def test_ancestor_custom_key_propagates(self):
        """Custom key names propagate to child tables."""
        data = {"a": {"subs": {"s1": {"val": 10}}}}
        tables = _convert(
            data,
            ["/:table:form:rptId", "/*/subs:table:sub:subId"],
        )
        sub_rows = tables[("form", "sub")]
        assert len(sub_rows) == 1
        row = sub_rows[0]
        assert "rptId" in row
        assert "subId" in row
        assert "form._key" not in row
        assert "form.sub._key" not in row


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


class TestNoHandlerSuggestion:
    """Error suggestions should use * for table key positions."""

    def test_one_table_level_array(self):
        """Unhandled nested object under an array table uses * for the table key."""
        data = [{"nested": {"a": 1}}]
        with pytest.raises(ConvertError, match=r"--path '/\*/nested"):
            _convert(data, ["/:table:item"])

    def test_one_table_level_object(self):
        """Unhandled nested object under an object table keeps the field name."""
        data = {"x": {"nested": {"a": 1}}}
        with pytest.raises(ConvertError, match=r"--path '/x/nested"):
            _convert(data, ["/:table:item"])

    def test_two_table_levels(self):
        """The original jsnell/json-to-multicsv#7 case."""
        data = [{"nested": {"z": 1, "a": [{"c": 2}]}}]
        with pytest.raises(ConvertError, match=r"--path '/\*/nested/a"):
            _convert(data, ["/:table:base", "/*/nested:table:nested"])

    def test_three_table_levels(self):
        """Deeply nested: array table keys become *, object keys stay concrete."""
        data = [{"mid": [{"deep": {"a": 1}}]}]
        with pytest.raises(ConvertError, match=r"--path '/\*/mid/\*/deep"):
            _convert(
                data,
                ["/:table:outer", "/*/mid:table:inner"],
            )
