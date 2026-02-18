"""Lexer/parser for path specs like '/:table:item'."""

from __future__ import annotations

from dataclasses import dataclass


class PathSpecError(ValueError):
    """Raised when a path spec is malformed."""


_VALID_KINDS = {"table", "column", "row", "ignore"}


@dataclass
class Handler:
    kind: str
    components: list[str]
    name: str | None = None
    key_name: str | None = None
    fallback: bool = False

    def matches(self, path: tuple[str, ...]) -> bool:
        if len(path) != len(self.components):
            return False
        return all(c == "*" or c == p for c, p in zip(self.components, path))


class _Lexer:
    """Demand-driven lexer for path specs."""

    def __init__(self, spec: str) -> None:
        self._spec = spec
        self._pos = 0

    def peek(self) -> str | None:
        if self._pos >= len(self._spec):
            return None
        return self._spec[self._pos]

    def error(self, message: str) -> PathSpecError:
        """Build a PathSpecError with a caret pointing at the current position."""
        pointer = " " * self._pos + "^"
        return PathSpecError(f"  {self._spec}\n  {pointer}\n{message}")

    def expect_char(self, ch: str) -> None:
        got = self.peek()
        if got != ch:
            got_desc = repr(got) if got is not None else "end of string"
            raise self.error(f"Expected {ch!r}, got {got_desc}")
        self._pos += 1

    def read_text(self) -> str:
        start = self._pos
        while self._pos < len(self._spec) and self._spec[self._pos] not in "/:":
            self._pos += 1
        if self._pos == start:
            got = self.peek()
            got_desc = repr(got) if got is not None else "end of string"
            raise self.error(f"Expected text, got {got_desc}")
        return self._spec[start : self._pos]

    def at_end(self) -> bool:
        return self._pos >= len(self._spec)


def parse_path_spec(spec: str) -> Handler:
    """Parse a --path value like '/:table:item' into a Handler."""
    lex = _Lexer(spec)

    # -- path: expect leading '/' --
    lex.expect_char("/")

    # -- segments --
    components: list[str] = []
    while lex.peek() not in (":", None):
        components.append(lex.read_text())
        if lex.peek() == "/":
            lex.expect_char("/")
            # Trailing slash before colon means empty segment
            if lex.peek() in (":", None):
                got = lex.peek()
                got_desc = repr(got) if got is not None else "end of string"
                raise lex.error(f"Expected text, got {got_desc}")

    # -- handler kind --
    lex.expect_char(":")
    kind = lex.read_text()
    if kind not in _VALID_KINDS:
        # Back up to point at the start of the bad kind
        lex._pos -= len(kind)
        raise lex.error(
            f"Unknown handler kind {kind!r}, "
            f"expected one of: {', '.join(sorted(_VALID_KINDS))}"
        )

    # -- name (only for table) --
    name: str | None = None
    key_name: str | None = None
    if kind == "table":
        lex.expect_char(":")
        name = lex.read_text()
        # -- optional key name --
        if lex.peek() == ":":
            lex.expect_char(":")
            key_name = lex.read_text()
    elif not lex.at_end():
        raise lex.error(f"'{kind}' handler does not take extra arguments")

    if not lex.at_end():
        raise lex.error("Unexpected content")

    return Handler(kind=kind, components=components, name=name, key_name=key_name)


def build_handlers(path_specs: list[str]) -> list[Handler]:
    """Parse path specs and expand into handler list with fallback column handlers."""
    handlers: list[Handler] = []
    for spec in path_specs:
        h = parse_path_spec(spec)
        handlers.append(h)
        handlers.append(
            Handler(
                kind="column",
                components=h.components + ["*"],
                fallback=True,
            )
        )
    return handlers
