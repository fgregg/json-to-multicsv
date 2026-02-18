"""Unit tests for path spec parsing via build_handlers."""

import pytest

from json_to_multicsv.parser import PathSpecError, build_handlers


def _parse(spec: str):
    """Parse a single spec and return the primary (non-fallback) handler."""
    handlers = build_handlers([spec])
    return [h for h in handlers if not h.fallback][0]


class TestValidSpecs:
    def test_root_table(self):
        h = _parse("/:table:item")
        assert h.kind == "table"
        assert h.components == []
        assert h.name == "item"

    def test_wildcard_column(self):
        h = _parse("/*/rating:column")
        assert h.kind == "column"
        assert h.components == ["*", "rating"]
        assert h.name is None

    def test_nested_table(self):
        h = _parse("/games:table:game")
        assert h.kind == "table"
        assert h.components == ["games"]
        assert h.name == "game"

    def test_deep_path_column(self):
        h = _parse("/games/*/players:column")
        assert h.kind == "column"
        assert h.components == ["games", "*", "players"]

    def test_root_row(self):
        h = _parse("/:row")
        assert h.kind == "row"
        assert h.components == []

    def test_ignore_handler(self):
        h = _parse("/secret:ignore")
        assert h.kind == "ignore"
        assert h.components == ["secret"]
        assert h.name is None

    def test_table_with_key_name(self):
        h = _parse("/:table:form:rptId")
        assert h.kind == "table"
        assert h.name == "form"
        assert h.key_name == "rptId"

    def test_table_without_key_name(self):
        h = _parse("/:table:form")
        assert h.kind == "table"
        assert h.name == "form"
        assert h.key_name is None


class TestInvalidSpecs:
    def test_missing_leading_slash(self):
        with pytest.raises(PathSpecError, match=r"Expected '/'"):
            build_handlers(["games:table:game"])

    def test_trailing_slash(self):
        with pytest.raises(PathSpecError, match=r"Expected text"):
            build_handlers(["/games/:table:game"])

    def test_unknown_handler_kind(self):
        with pytest.raises(PathSpecError, match="Unknown handler kind"):
            build_handlers(["/:bogus"])

    def test_table_without_name(self):
        with pytest.raises(PathSpecError, match=r"Expected ':'"):
            build_handlers(["/:table"])

    def test_column_with_name(self):
        with pytest.raises(PathSpecError, match="does not take extra arguments"):
            build_handlers(["/foo:column:bar"])

    def test_empty_segment_double_slash(self):
        with pytest.raises(PathSpecError, match=r"Expected text"):
            build_handlers(["//foo:column"])

    def test_missing_handler(self):
        with pytest.raises(PathSpecError, match=r"Expected ':'"):
            build_handlers(["/foo"])

    def test_too_many_parts(self):
        with pytest.raises(PathSpecError, match="Unexpected content"):
            build_handlers(["/:table:name:key:extra"])

    def test_empty_key_name(self):
        with pytest.raises(PathSpecError, match=r"Expected text"):
            build_handlers(["/:table:name:"])

    def test_bare_root_no_handler(self):
        with pytest.raises(PathSpecError, match=r"Expected ':'"):
            build_handlers(["/"])
