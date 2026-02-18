"""Tests ported from the Perl json-to-multicsv test suite.

Each test invokes the CLI with the same flags as the Perl tests,
then compares byte-for-byte against the expected CSV outputs.
"""

from pathlib import Path

from click.testing import CliRunner

from json_to_multicsv.cli import main

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_expected_csvs(name):
    """Load expected CSV outputs for a test case.

    Returns dict mapping filename -> bytes.
    """
    expected_dir = FIXTURES_DIR / name / "output.expected"
    return {
        csv_file.name: csv_file.read_bytes()
        for csv_file in sorted(expected_dir.glob("*.csv"))
    }


def _run_test(name, cli_args, tmp_path):
    """Run a test case: invoke CLI, compare outputs."""
    input_path = FIXTURES_DIR / name / "input.json"
    expected_csvs = _load_expected_csvs(name)

    runner = CliRunner()
    args = ["--file", str(input_path)] + cli_args
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        result = runner.invoke(main, args)
        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}\n"
            f"Output: {result.output}\n"
            f"Exception: {result.exception}"
        )

        td = Path(td)
        for filename, expected_bytes in expected_csvs.items():
            actual_path = td / filename
            assert actual_path.exists(), f"Expected output file {filename} not created"
            actual_bytes = actual_path.read_bytes()
            assert actual_bytes == expected_bytes, (
                f"Mismatch in {filename}:\n"
                f"Expected:\n{expected_bytes!r}\n"
                f"Actual:\n{actual_bytes!r}"
            )


def test_basic(tmp_path):
    """Nested objects/arrays with multiple tables, column flattening, booleans."""
    _run_test(
        "basic",
        [
            "--path",
            "/:table:item",
            "--path",
            "/*/rating:column",
            "--path",
            "/*/sales:table:sales",
            "--path",
            "/*/appendix:table:appendix",
            "--path",
            "/*/genres:table:genres",
        ],
        tmp_path,
    )


def test_binary(tmp_path):
    """Special characters: CRLF, newlines, Unicode."""
    _run_test(
        "binary",
        [
            "--path",
            "/:table:main",
        ],
        tmp_path,
    )


def test_column_list(tmp_path):
    """Arrays flattened to columns (fixed-size array expansion)."""
    _run_test(
        "column-list",
        [
            "--path",
            "/:table:shapes",
            "--path",
            "/*/points:column",
            "--path",
            "/*/points/0:column",
            "--path",
            "/*/points/1:column",
        ],
        tmp_path,
    )


def test_tmtour(tmp_path):
    """Row handler at root with --table, nested tables and column arrays."""
    _run_test(
        "tmtour",
        [
            "--path",
            "/:row",
            "--path",
            "/games:table:game",
            "--path",
            "/games/*/players:column",
            "--path",
            "/options:table:option",
            "--table",
            "main",
        ],
        tmp_path,
    )


def test_toplevel_list(tmp_path):
    """Top-level JSON array as table."""
    _run_test(
        "toplevel-list",
        [
            "--path",
            "/:table:greetings",
        ],
        tmp_path,
    )


def test_key_name(tmp_path):
    """Custom key column names via path spec, with propagation to child tables."""
    _run_test(
        "key-name",
        [
            "--path",
            "/:table:item:itemId",
            "--path",
            "/*/subs:table:sub:subId",
        ],
        tmp_path,
    )


def test_no_prefix(tmp_path):
    """--no-prefix uses only the last table name component for filenames."""
    input_path = FIXTURES_DIR / "basic" / "input.json"
    expected_csvs = _load_expected_csvs("basic")

    runner = CliRunner()
    args = [
        "--file",
        str(input_path),
        "--no-prefix",
        "--path",
        "/:table:item",
        "--path",
        "/*/rating:column",
        "--path",
        "/*/sales:table:sales",
        "--path",
        "/*/appendix:table:appendix",
        "--path",
        "/*/genres:table:genres",
    ]
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        result = runner.invoke(main, args)
        assert result.exit_code == 0, (
            f"CLI exited with code {result.exit_code}\n"
            f"Output: {result.output}\n"
            f"Exception: {result.exception}"
        )

        td = Path(td)
        # With --no-prefix, "item.sales.csv" becomes "sales.csv", etc.
        for prefixed_name, expected_bytes in expected_csvs.items():
            short_name = prefixed_name.rsplit(".", 1)[0].split(".")[-1] + ".csv"
            actual_path = td / short_name
            assert (
                actual_path.exists()
            ), f"Expected output file {short_name} not created"
            assert actual_path.read_bytes() == expected_bytes


def test_no_prefix_duplicate_error(tmp_path):
    """--no-prefix raises an error when two tables share the same short name."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        td = Path(td)
        # Create JSON where two different table paths produce "item" as leaf name:
        # ('top', 'item') and ('top', 'thing', 'item')
        (td / "input.json").write_text('{"a": {"x": [1, 2], "y": [{"z": [10, 20]}]}}')
        args = [
            "--file",
            str(td / "input.json"),
            "--no-prefix",
            "--path",
            "/:table:top",
            "--path",
            "/*/x:table:item",
            "--path",
            "/*/y:table:thing",
            "--path",
            "/*/y/*/z:table:item",
        ]
        result = runner.invoke(main, args)
        assert result.exit_code != 0
        assert "duplicate table name" in result.output
        assert "--path '/*/y/*/z:table:item_2'" in result.output
