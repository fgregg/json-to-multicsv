"""Command-line interface for json-to-multicsv."""

import csv
import re

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
@click.option(
    "--no-prefix",
    "no_prefix",
    is_flag=True,
    default=False,
    help="Use only the last component of the table name for output filenames.",
)
def main(input_file, paths, table_name, no_prefix):
    """Split a JSON file with hierarchical data to multiple CSV files."""
    try:
        handlers = build_handlers(paths)
    except PathSpecError as e:
        raise click.BadParameter("\n" + str(e), param_hint="'--path'") from None
    try:
        tables = json_to_multicsv(input_file, handlers, table_name)
    except ConvertError as e:
        raise click.BadParameter(str(e), param_hint="'--path'") from None

    if no_prefix:
        short_names = [parts[-1] for parts in tables]
        seen = {}
        for name, parts in zip(short_names, tables):
            if name in seen:
                conflicting = ".".join(seen[name])
                current = ".".join(parts)

                # Find the last --path that defines a table with this name
                # and suggest a concrete rewrite with a different name.
                suggestion = f"  --path '...:table:{name}_2'"
                pattern = re.compile(
                    r"^(?P<prefix>.+:table:)" + re.escape(name) + r"(?P<suffix>:.+)?$"
                )
                for path_spec in reversed(paths):
                    m = pattern.match(path_spec)
                    if m:
                        suffix = m.group("suffix") or ""
                        suggestion = f"  --path '{m.group('prefix')}{name}_2{suffix}'"
                        break

                raise click.ClickException(
                    f"--no-prefix: duplicate table name '{name}' "
                    f"from '{conflicting}' and '{current}'.\n"
                    f"To fix, rename one of the tables, e.g.:\n"
                    f"{suggestion}"
                )
            seen[name] = parts

    for table_parts, rows in tables.items():
        # Unique column names in insertion order (keys first, then data).
        fields = list(dict.fromkeys(k for row in rows for k in row))
        filename = (
            table_parts[-1] + ".csv" if no_prefix else ".".join(table_parts) + ".csv"
        )
        with open(filename, "w") as f:
            writer = csv.DictWriter(f, fieldnames=fields, restval="")
            writer.writeheader()
            writer.writerows(rows)
