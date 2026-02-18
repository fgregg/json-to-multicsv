"""Command-line interface for json-to-multicsv."""

import csv

import click

from .converter import ConvertError, json_to_multicsv
from .parser import PathSpecError, build_handlers


@click.command()
@click.option(
    "--file",
    "input_file",
    default="-",
    type=click.File(encoding="utf-8"),
    help="JSON input file (default: stdin)",
)
@click.option("--path", "paths", multiple=True, help="pathspec:handler[:name]")
@click.option("--table", "table_name", default=None, help="Top-level table name")
def main(input_file, paths, table_name):
    """Split a JSON file with hierarchical data to multiple CSV files."""
    try:
        handlers = build_handlers(paths)
    except PathSpecError as e:
        raise click.BadParameter("\n" + str(e), param_hint="'--path'") from None
    try:
        tables = json_to_multicsv(input_file, handlers, table_name)
    except ConvertError as e:
        raise click.BadParameter(str(e), param_hint="'--path'") from None

    for table_parts, rows in tables.items():
        # Unique column names in insertion order (keys first, then data).
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with open(f"{'.'.join(table_parts)}.csv", "w") as f:
            writer = csv.DictWriter(f, fieldnames=fields, restval="")
            writer.writeheader()
            writer.writerows(rows)
