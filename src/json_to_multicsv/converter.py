"""Core conversion logic for json-to-multicsv.

JSON objects are decoded with a custom object_pairs_hook that sorts
keys at decode time.  The Converter then walks the decoded tree
top-down, applying path-based handlers to build the output tables.
"""

import json
from collections import defaultdict

from json_to_multicsv.parser import Handler


class ConvertError(Exception):
    """Raised when the converter encounters data it cannot handle."""


def _sorted_dict(items: list[tuple[str, object]]) -> dict:
    return dict(sorted(items))


class Converter:
    """Walks a decoded JSON tree top-down, collecting rows into tables."""

    def __init__(
        self,
        handlers: list[Handler],
        table_name: str | None = None,
    ):
        self.handlers = handlers
        self.tables: defaultdict[tuple[str, ...], list[dict]] = defaultdict(list)
        self._initial_table_parts = (table_name,) if table_name else ()

    def convert(self, fileobj) -> dict[tuple[str, ...], list[dict]]:
        data = json.load(fileobj, object_pairs_hook=_sorted_dict)
        self._walk(
            data,
            path=(),
            key=(),
            key_names=(),
            table_parts=self._initial_table_parts,
            field=None,
            row=None,
        )
        return self.tables

    # -- internal machinery ---------------------------------------------------

    def _find_handler(self, path: tuple[str, ...]) -> Handler | None:
        fallback = None
        for handler in self.handlers:
            if handler.matches(path):
                if handler.fallback:
                    fallback = handler
                else:
                    return handler
        return fallback

    def _new_row(self, key_names: tuple[str, ...], key: tuple) -> dict:
        """Create a row pre-populated with ancestor key columns."""
        row: dict = {}
        for i, k in enumerate(key):
            row[key_names[i]] = k
        return row

    def _walk(self, val, *, path, key, key_names, table_parts, field, row):
        handler = self._find_handler(path)

        if handler and handler.kind == "ignore":
            return

        # Scalars go directly into the current row.
        if not isinstance(val, dict | list):
            if field in row:
                json_path = "/" + "/".join(path)
                raise ConvertError(
                    f"Column name {field!r} already exists in table "
                    f"{'.'.join(table_parts)!r} at {json_path}\n"
                    f"This can happen when a JSON key contains '.' and "
                    f"collides with a flattened nested path."
                )
            row[field] = val
            return

        if not handler:
            json_path = "/" + "/".join(path)
            val_type = "object" if isinstance(val, dict) else "array"
            raise ConvertError(
                f"No handler matches the {val_type} at {json_path}\n"
                f"Add a --path option for this location, for example:\n"
                f"  --path '{json_path}:table:NAME'\n"
                f"  --path '{json_path}:column'\n"
                f"  --path '{json_path}:ignore'"
            )

        # Normalize objects and lists into (key, value) pairs.
        if isinstance(val, dict):
            children = val.items()
        else:
            children = ((str(i), v) for i, v in enumerate(val))

        match handler.kind:
            case "table":
                tbl_name = handler.name
                child_parts = table_parts + (tbl_name,)
                if handler.key_name:
                    col_name = handler.key_name
                else:
                    col_name = ".".join(child_parts[: len(key) + 1]) + "._key"
                child_key_names = key_names + (col_name,)
                for child_key, child in children:
                    child_keys = key + (child_key,)
                    child_row = self._new_row(child_key_names, child_keys)
                    self.tables[child_parts].append(child_row)
                    if not isinstance(child, dict | list):
                        child_row[tbl_name] = child
                    else:
                        self._walk(
                            child,
                            path=path + (child_key,),
                            key=child_keys,
                            key_names=child_key_names,
                            table_parts=child_parts,
                            field=None,
                            row=child_row,
                        )

            case "column":
                for child_key, child in children:
                    self._walk(
                        child,
                        path=path + (child_key,),
                        key=key,
                        key_names=key_names,
                        table_parts=table_parts,
                        field=(
                            f"{field}.{child_key}" if field is not None else child_key
                        ),
                        row=row,
                    )

            case "row":
                new_row = self._new_row(key_names, key)
                self.tables[table_parts].append(new_row)
                for child_key, child in children:
                    self._walk(
                        child,
                        path=path + (child_key,),
                        key=key,
                        key_names=key_names,
                        table_parts=table_parts,
                        field=child_key,
                        row=new_row,
                    )


def json_to_multicsv(
    fileobj, handlers: list[Handler], table_name: str | None = None
) -> dict[tuple[str, ...], list[dict]]:
    """Parse a JSON file and convert into a dict of named row lists."""
    return Converter(handlers, table_name).convert(fileobj)
