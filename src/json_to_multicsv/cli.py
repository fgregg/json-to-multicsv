"""Command-line interface for json-to-multicsv."""

import csv
import re

import click

from .converter import ConvertError, json_to_multicsv
from .parser import PathSpecError, build_handlers


def _parse_paths(ctx, param, value):
    """Click callback: parse --path specs into Handler objects eagerly."""
    ctx.ensure_object(dict)
    ctx.obj["raw_paths"] = value
    try:
        return build_handlers(value)
    except PathSpecError as e:
        raise click.BadParameter("\n" + str(e), param_hint="'--path'") from None


def _check_no_prefix_collisions(handlers, table_name, raw_paths):
    """Check for duplicate leaf table names when --no-prefix is used."""
    seen = {}  # name -> source description

    # Check if a root row handler exists (components == [])
    has_root_row = any(h.kind == "row" and h.components == [] for h in handlers)
    if has_root_row:
        if not table_name:
            raise click.ClickException(
                "--no-prefix requires --table when using a root '/:row' handler"
            )
        seen[table_name] = table_name

    for handler in handlers:
        if handler.kind == "table":
            name = handler.name
            if name in seen:
                suggestion = f"  --path '...:table:{name}_2'"
                pattern = re.compile(
                    r"^(?P<prefix>.+:table:)" + re.escape(name) + r"(?P<suffix>:.+)?$"
                )
                for path_spec in reversed(raw_paths):
                    m = pattern.match(path_spec)
                    if m:
                        suffix = m.group("suffix") or ""
                        suggestion = f"  --path '{m.group('prefix')}{name}_2{suffix}'"
                        break

                raise click.ClickException(
                    f"--no-prefix: duplicate table name '{name}'.\n"
                    f"To fix, rename one of the tables, e.g.:\n"
                    f"{suggestion}"
                )
            seen[name] = name


@click.command()
@click.pass_context
@click.option(
    "--file",
    "input_file",
    default="-",
    type=click.File(encoding="utf-8"),
    help="JSON input file (default: stdin)",
)
@click.option(
    "--path",
    "handlers",
    multiple=True,
    callback=_parse_paths,
    help="pathspec:handler[:name]",
)
@click.option("--table", "table_name", default=None, help="Top-level table name")
@click.option(
    "--no-prefix",
    "no_prefix",
    is_flag=True,
    default=False,
    help="Use only the last component of the table name for output filenames.",
)
def main(ctx, input_file, handlers, table_name, no_prefix):
    """Split a JSON file with hierarchical data to multiple CSV files."""
    if no_prefix:
        _check_no_prefix_collisions(handlers, table_name, ctx.obj["raw_paths"])

    try:
        tables = json_to_multicsv(input_file, handlers, table_name)
    except ConvertError as e:
        raise click.BadParameter(str(e), param_hint="'--path'") from None

    for table_parts, rows in tables.items():
        # Unique column names in insertion order (keys first, then data).
        fields = list(dict.fromkeys(k for row in rows for k in row))
        filename = f"{table_parts[-1] if no_prefix else ".".join(table_parts)}.csv"
        with open(filename, "w") as f:
            writer = csv.DictWriter(f, fieldnames=fields, restval="")
            writer.writeheader()
            writer.writerows(rows)
