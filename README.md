# csv

CSV tables with named columns for Sarlin 0.1.6 and newer. No package dependencies.

Sarlin already provides `CSV.parse` and `CSV.stringify` for raw `string[][]` data.
This package adds a header row, column lookup, rectangular-table validation and
file helpers. Values remain strings, so leading zeroes and empty fields survive.

## Example

```sarlin
func main() {
    local var headers string[] = ["name", "score", "note"]
    local var rows string[][] = [
        ["Alice", "1200", "London, UK"],
        ["Bob", "850", ""]
    ]
    local var result CsvTableResult = csv_from_rows(headers, rows)
    if result.error != "" {
        print(result.error)
        return
    }

    local var score_column int64 = result.table.column_index("score")
    for row in result.table.rows {
        print(row[0] + ": " + row[score_column])
    }

    local var error string = csv_write("scores.csv", result.table)
    if error != "" {
        print(error)
    }
}
```

Read a file with `csv_read("scores.csv")`, or parse existing text with
`csv_parse(text)`. Both return a `CsvTableResult`; check `error` before accessing
`table`. No import statement is needed.

## API

| Function | Result |
| --- | --- |
| `csv_from_rows(headers string[], rows string[][])` | `CsvTableResult`; validates and copies the input, including nested rows. |
| `csv_parse(text string)` | `CsvTableResult`; consumes the first record as headers. |
| `csv_read(filename string)` | `CsvTableResult`; reads a complete file and parses it. |
| `csv_stringify(table CsvTable)` | `CsvTextResult`; validates and serializes headers followed by rows. |
| `csv_write(filename string, table CsvTable)` | Empty string on success, or a table-validation error. Creates or replaces the file after validation. |
| `table.column_index(name string)` | `int64`; zero-based column index, or `-1` when absent. Check before indexing, since Sarlin accepts negative array indexes. |
| `table.validate()` | Empty string if valid, otherwise a description of the first problem. |

`CsvTable` has mutable `headers string[]` and `rows string[][]` fields. Rows do
not include the headers. You can update cells or append rows using normal array
operations. Serialization validates again, so invalid edits cannot be written
through `csv_write`.

`CsvTableResult` contains `table CsvTable` and `error string`. Package functions
return a null table on validation failure. `CsvTextResult` contains `text string`
and `error string`; text is empty on validation failure. For both result types,
an empty error means success.

## Data rules and errors

- A table needs one or more headers, each nonempty and not whitespace-only. An empty document
  is a validation error; a header-only document is valid.
- Header names must be unique. Matching is case-sensitive and preserves spaces:
  `name` and ` name ` are different columns. Nothing is trimmed or converted.
- Every data row must have exactly as many fields as the header row. Error row
  numbers count data records from one, including records containing line breaks.
- Commas, doubled quotes, quoted line breaks, UTF-8 text and empty fields are
  supported by Sarlin's built-in CSV codec. The delimiter is always a comma;
  output uses LF separators and has no final record separator.
- The package explicitly quotes a lone empty field so spreadsheet and other CSV
  readers preserve single-column empty records.
- `csv_stringify(null)` and `csv_write(filename, null)` return validation errors.
  Invalid tables neither create a file nor replace an existing one.

Malformed CSV syntax and filesystem failures follow Sarlin's built-in behavior:
they terminate the program with a runtime diagnostic. They are **not** returned
in `error`. For example, unterminated quoted fields and unreadable files are
fatal. Parent directories must exist before writing. Successful writes replace
the destination and are not atomic. The package reads and encodes whole tables
in memory; it does not stream large files.

## Installation

Add the package directly from GitHub:

```sh
sarlin add github.com/TheRealSarin/sarlin-csv
```

or from the Nook:

```sh
sarlin add csv@0.1.2
```

Both commands add the dependency to your project's `sarlin.project` and pin its
commit in `sarlin.lock`. Commit both files with your project.

## Local use and tests

For local use before publication, copy `source/csv.sar` into your
project's `source/` folder. Keep `examples/` and `tests/` outside your project's
`source/` folder so their entry points are not compiled into your program.

Run the tests from this directory with Python 3 and Sarlin 0.1.6+:

```sh
python3 tests/run.py --sarlin /path/to/sarlin
```

In this workspace, the current compiler can be selected explicitly:

```sh
python3 tests/run.py --sarlin ../../sarlin-compiler/target/debug/sarlin
```

The runner uses temporary directories and an isolated, prepopulated Nook cache
to compile consumer projects with a real `require: csv 0.1.0` dependency. Its
synthetic lock entry is only a test fixture; it does not publish or fetch a
release. Tests cover parsing and writing, quoted and multiline fields, line
endings, header validation, row widths, copy ownership, invalid writes, fatal
diagnostics and the runnable [scores example](examples/scores.sar). Python's
standard CSV reader independently verifies input and output records. No Python
dependencies or network access are needed.

The package's `source/` contains no `main` function, as required by Sarlin.
Check or build it through a consumer project; running `sarlin check .` directly
requires an executable entry point and will report that `main` is missing.

## License

Licensed under the [MIT License](LICENSE).

Copyright (c) 2026 Florin Sarca.
