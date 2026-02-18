# json-to-multicsv

Split a JSON file with hierarchical data into multiple CSV files.

A Python rewrite of [jsnell/json-to-multicsv](https://github.com/jsnell/json-to-multicsv).

## Installation

```
pip install json-to-multicsv
```

## Usage

```
$ json-to-multicsv --help
Usage: json-to-multicsv [OPTIONS]

  Split a JSON file with hierarchical data to multiple CSV files.

Options:
  --file FILENAME  JSON input file (default: stdin)
  --path TEXT      pathspec:handler[:name]
  --table TEXT     Top-level table name
  --no-prefix      Use only the last component of the table name for output
                   filenames.
  --help           Show this message and exit.
```

## Examples

### Nested objects and arrays

Given this input:

```json
{
    "item 1": {
        "title": "The First Item",
        "genres": ["sci-fi", "adventure"],
        "rating": {
            "mean": 9.5,
            "votes": 190
        }
    },
    "item 2": {
        "title": "The Second Item",
        "genres": ["history", "economics"],
        "rating": {
            "mean": 7.4,
            "votes": 865
        },
        "sales": [
            { "count": 76, "country": "us" },
            { "count": 13, "country": "de" },
            { "count": 4, "country": "fi" }
        ]
    }
}
```

```
json-to-multicsv --file input.json \
    --path '/:table:item' \
    --path '/*/rating:column' \
    --path '/*/sales:table:sales' \
    --path '/*/genres:table:genres'
```

Produces three CSV files, joinable on the `*._key` columns:

**item.csv**:

```
item._key,rating.mean,rating.votes,title
item 1,9.5,190,The First Item
item 2,7.4,865,The Second Item
```

**item.genres.csv**:

```
item._key,item.genres._key,genres
item 1,0,sci-fi
item 1,1,adventure
item 2,0,history
item 2,1,economics
```

**item.sales.csv**:

```
item._key,item.sales._key,count,country
item 2,0,76,us
item 2,1,13,de
item 2,2,4,fi
```

### Row handler, custom key names, and ignore

When the top-level JSON value is a single object (not a collection),
use `/:row` with `--table` to name the output table. Custom key column
names can be set with an extra `:KEY_NAME` argument on table handlers.
Use `:ignore` to skip parts of the data.

```json
{
    "name": "Summer Championship",
    "year": 2024,
    "games": {
        "game-1": {
            "home": "Eagles",
            "away": "Hawks",
            "score": { "home": 3, "away": 1 }
        },
        "game-2": {
            "home": "Bears",
            "away": "Lions",
            "score": { "home": 2, "away": 2 }
        }
    },
    "sponsors": ["Acme Corp", "Globex"]
}
```

```
json-to-multicsv --file tournament.json \
    --path '/:row' \
    --path '/games:table:game:gameId' \
    --path '/games/*/score:column' \
    --path '/sponsors:ignore' \
    --table main
```

**main.csv**:

```
name,year
Summer Championship,2024
```

**main.game.csv**:

```
gameId,away,home,score.away,score.home
game-1,Hawks,Eagles,1,3
game-2,Lions,Bears,2,2
```

Note that `gameId` replaces the default `game._key` column name, and
sponsors are omitted entirely.

### Top-level array

When the input is a JSON array, a single `table` handler at the root
is all you need:

```json
[
    {"title": "Dune", "author": "Frank Herbert", "year": 1965},
    {"title": "Neuromancer", "author": "William Gibson", "year": 1984},
    {"title": "Snow Crash", "author": "Neal Stephenson", "year": 1992}
]
```

```
json-to-multicsv --file books.json --path '/:table:book'
```

**book.csv**:

```
book._key,author,title,year
0,Frank Herbert,Dune,1965
1,William Gibson,Neuromancer,1984
2,Neal Stephenson,Snow Crash,1992
```

## Options

### `--file INPUT`

Read JSON input from a file. Defaults to stdin.

### `--path PATHSPEC:table:NAME[:KEY_NAME]`

Values matching the pathspec open a new table with the given name. The
value should be an object or array. For objects, each field produces a
row, with the field name stored in the `NAME._key` column. For arrays,
each element produces a row, with the 0-based index stored in the
`NAME._key` column.

When tables are nested, key columns from all outer tables are included
in inner tables.

An optional key name can be provided to customize the key column name
(e.g., `/:table:item:itemId` produces an `itemId` column instead of
`item._key`).

### `--path PATHSPEC:column`

Values matching the pathspec are emitted as columns in the current
table's row. If the value is a scalar, it becomes a single column. If
the value is an object, its fields are flattened into multiple columns
with dotted names.

### `--path PATHSPEC:row`

Values matching the pathspec are emitted as new rows in the current
table. The value must be an object. This is generally only useful for
the top-level JSON value, combined with `--table`.

### `--path PATHSPEC:ignore`

Values matching the pathspec (and all their children) are skipped.

### `--table NAME`

Name the top-level table. Use this with a `row` handler on the root
element.

### `--no-prefix`

Use only the last component of the table name for output filenames.
For example, `item.sales.csv` becomes `sales.csv`.

## Paths and pathspecs

The path to a JSON value is determined by:

- The root element's path is `/`
- For values inside an object: parent path + `/` + field name
- For values inside an array: parent path + `/` + 0-based index

In a pathspec, any path component can be replaced with `*`, which
matches any single component. For example, `/a/*/c` matches `/a/b/c`
but not `/a/b/b/c`.

## License

MIT. Based on [json-to-multicsv](https://github.com/jsnell/json-to-multicsv) by Juho Snellman.
