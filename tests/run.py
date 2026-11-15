"""Build and test csv with a native Sarlin compiler; no third-party tools required."""

import argparse
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


PACKAGE = Path(__file__).resolve().parents[1]
# Synthetic lock entry for an isolated, prepopulated package cache; never fetched.
TEST_COMMIT = "0" * 40
TEST_REPOSITORY = "https://github.com/sarlin-csv-tests/csv"


def run(command, cwd, env=None):
    result = subprocess.run(
        [str(item) for item in command],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {command}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result.stdout


def stage_project(root, main):
    source = root / "source"
    source.mkdir()
    (source / "main.sar").write_text(main, encoding="utf-8")
    (root / "sarlin.project").write_text(
        "name: Csv Tests\nentry: source/main.sar\nlanguage: 1\nrequire: csv 0.1.0\n",
        encoding="utf-8",
    )
    (root / "sarlin.lock").write_text(
        f"sarlin-lock 1\ncsv 0.1.0 {TEST_REPOSITORY} {TEST_COMMIT}\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sarlin", default="sarlin", help="Sarlin 0.1.3+ executable")
    args = parser.parse_args()
    compiler = shutil.which(args.sarlin)
    if compiler is None:
        parser.error(f"Compiler not found: {args.sarlin}")
    compiler = Path(compiler).resolve()
    suffix = ".exe" if os.name == "nt" else ""

    documents = {
        "basic": "name,score\nAlice,1200\nBob,850\n",
        "crlf": "name,note\r\nAlice,hello\r\n",
        "quotes": 'name,note\nAlice,"London, UK"\nBob,"says ""hello"""\n',
        "multiline": 'name,note\nAlice,"line one\nline two"\nBob,"a\r\nb"\n',
        "empty_fields": 'name,note\n,\nAlice,\n,""\n',
        "header_only": "name,score",
        "single_column": 'name\nAlice\n""\nBob',
        "single_empty_last": 'name\nAlice\n""',
        "single_empty_only": 'name\n""',
        "no_final_newline": "name,score\nAlice,1200",
        "unicode": "name,note\nZoë,東京 🐦\n",
        "spaces": " name ,note\n Alice , keep spaces \n",
        "quoted_headers": '"full,name","say ""hi"""\nAlice,hello\n',
        "bare_cr": "name,note\rAlice,hello\r",
    }

    with tempfile.TemporaryDirectory(prefix="sarlin-csv-") as temporary:
        root = Path(temporary)
        cache = root / "nook"
        cached_package = cache / "packages" / f"csv-0.1.0-{TEST_COMMIT[:12]}"
        shutil.copytree(PACKAGE / "source", cached_package / "source")
        shutil.copyfile(PACKAGE / "sarlin.project", cached_package / "sarlin.project")
        environment = {**os.environ, "SARLIN_NOOK_HOME": str(cache)}
        stage_project(root, (PACKAGE / "tests/main.sar").read_text(encoding="utf-8"))
        for name, document in documents.items():
            folder = root / "cases" / name
            folder.mkdir(parents=True)
            (folder / "input.csv").write_bytes(document.encode("utf-8"))
            expected = list(csv.reader(io.StringIO(document, newline=""), strict=True))
            (folder / "expected.json").write_text(json.dumps(expected), encoding="utf-8")
        (root / "ragged.csv").write_bytes(b"name,score\nAlice,1200\nBob\n")

        executable = root / ("csv-tests" + suffix)
        run([compiler, "check", root], root, environment)
        if run([compiler, "collisions", root], root, environment) != "no collisions found\n":
            raise AssertionError("Package name collisions")
        run([compiler, "build", root, "--output", executable], root, environment)
        output = run([executable], root)
        if output != "csv tests passed\n":
            raise AssertionError(output)
        for name in documents:
            folder = root / "cases" / name
            with (folder / "output.csv").open(encoding="utf-8", newline="") as encoded:
                actual = list(csv.reader(encoded, strict=True))
            expected = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
            if actual != expected:
                raise AssertionError(
                    f"Python CSV interoperability failed: {name}: {actual!r} != {expected!r}; "
                    f"encoded bytes: {(folder / 'output.csv').read_bytes()!r}"
                )

        # Keep fatal built-in errors in separate processes so the suite continues.
        failure_root = root / "failures"
        failure_root.mkdir()
        stage_project(failure_root, 'func main() {\n    csv_read("input.csv")\n}\n')
        failure_executable = failure_root / ("read-failure" + suffix)
        run([compiler, "build", failure_root, "--output", failure_executable], root, environment)
        for name, document in {
            "missing file": None,
            "unterminated quote": 'name\n"unfinished',
            "quote in unquoted field": 'name\nbad"quote',
            "text after closing quote": 'name\n"value"extra',
        }.items():
            if document is not None:
                (failure_root / "input.csv").write_text(document, encoding="utf-8")
            result = subprocess.run(
                [str(failure_executable)], cwd=failure_root,
                capture_output=True, text=True, timeout=30, check=False,
            )
            if result.returncode == 0 or "runtime error:" not in result.stderr:
                raise AssertionError(f"Expected a runtime diagnostic for {name}: {result}")

        example_root = root / "example"
        example_root.mkdir()
        stage_project(example_root, (PACKAGE / "examples/scores.sar").read_text(encoding="utf-8"))
        example_executable = example_root / ("scores" + suffix)
        run([compiler, "build", example_root, "--output", example_executable], root, environment)
        example_output = run([example_executable], root)
        expected_example = 'Alice: 1200\nBob: 850\nname,score,note\nAlice,1200,"London, UK"\nBob,850,\n'
        if example_output != expected_example:
            raise AssertionError(f"Unexpected example output: {example_output!r}")

    print(f"Passed: {len(documents)} CSV fixtures, table validation and ownership, file I/O,")
    print("Python CSV interoperability, 4 fatal error cases, and the example.")
    print("Package loading and collision checks passed using an isolated offline cache.")


if __name__ == "__main__":
    main()
