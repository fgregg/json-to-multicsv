"""Command-line interface for json-to-multicsv."""

import csv

import click

from .converter import build_handlers, json_to_multicsv


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
    handlers = build_handlers(paths)
    tables = json_to_multicsv(input_file, handlers, table_name)

    for table_parts, rows in tables.items():
        fields = sorted({k for row in rows for k in row})
        with open(f"{'.'.join(table_parts)}.csv", "w") as f:
            writer = csv.DictWriter(f, fieldnames=fields, restval="")
            writer.writeheader()
            writer.writerows(rows)
