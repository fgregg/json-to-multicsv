"""Fuzz tests for the path spec parser.

The parser must never raise anything other than PathSpecError for bad input,
and must never crash (no IndexError, TypeError, etc.). For valid specs it
must return a well-formed Handler.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from json_to_multicsv.parser import Handler, PathSpecError, parse_path_spec

# -- building blocks ----------------------------------------------------------

segment = st.from_regex(r"[^/:]+", fullmatch=True)
wildcard = st.just("*")
path_segment = st.one_of(segment, wildcard)

valid_kind = st.sampled_from(["table", "column", "row", "ignore"])
table_name = st.from_regex(r"[^/:]+", fullmatch=True)


# -- strategy: structurally valid specs ---------------------------------------


@st.composite
def valid_specs(draw):
    """Generate specs that should always parse successfully."""
    segments = draw(st.lists(path_segment, min_size=0, max_size=5))
    kind = draw(valid_kind)

    path = "/" + "/".join(segments)
    spec = path + ":" + kind

    if kind == "table":
        name = draw(table_name)
        spec += ":" + name

    return spec


# -- strategy: arbitrary garbage ----------------------------------------------

garbage = st.text(
    alphabet=st.sampled_from("/:*abcXY 01\t\n\x00"),
    min_size=0,
    max_size=50,
)


# -- tests --------------------------------------------------------------------


class TestFuzzParser:
    @given(spec=valid_specs())
    @settings(max_examples=1000)
    def test_valid_specs_parse_successfully(self, spec):
        """Structurally valid specs must always produce a Handler."""
        h = parse_path_spec(spec)
        assert isinstance(h, Handler)
        assert h.kind in ("table", "column", "row", "ignore")
        if h.kind == "table":
            assert h.name is not None
        else:
            assert h.name is None

    @given(spec=garbage)
    @settings(max_examples=5000)
    def test_garbage_never_crashes(self, spec):
        """Arbitrary input must raise PathSpecError or succeed — never crash."""
        try:
            h = parse_path_spec(spec)
            # If it parsed, it should be well-formed
            assert isinstance(h, Handler)
            assert h.kind in ("table", "column", "row", "ignore")
        except PathSpecError:
            pass  # expected for bad input

    @given(spec=st.text(min_size=0, max_size=100))
    @settings(max_examples=5000)
    def test_fully_random_text_never_crashes(self, spec):
        """Full unicode range — must not raise anything unexpected."""
        try:
            parse_path_spec(spec)
        except PathSpecError:
            pass
