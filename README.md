# paperlint

paperlint checks a LaTeX paper against my personal rules of style in [`style.tex`](style.tex). It reads the source. It does not compile the paper.

The style is opinionated: REVTeX-style papers, `\cref`, `\qty` and `\num`, `multline` for a broken equation, `booktabs` tables, and citation commands that distinguish a parenthetical `\cite` from a citation used as a word (`\refcite`, `\refscite`). What the checker does is listed in [`docs/behavior.md`](docs/behavior.md). The reasons for those choices are in [`docs/adr/0001-checking-model.md`](docs/adr/0001-checking-model.md).

## Install

Python 3.11 or newer:

```bash
pip install -e .
```

Run that from a clone of [this repository](https://github.com/benvlehmann/paperlint). The package is not published on PyPI.

## Usage

Pass the root file. paperlint follows `\input` and `\include` from there, and does not read `.bbl` or `.aux` files.

```bash
paperlint main.tex
```

Each finding is one line:

```text
main.tex:12:5: error: use \cref instead of \ref [no-ref]
```

The process exits 1 when any finding is an error. Warnings alone exit 0.

A chapter checked by itself starts with an empty environment stack. Lint the root file when the paper is split across files.

### Configuration

An optional `paperlint.toml` next to the root file replaces any of these defaults: label prefixes, citation trigger and exclusion lists, abbreviations, and the comment-line threshold.

```toml
comment_line_threshold = 6
exclusions = ["e.g.", "i.e.", "etc.", "al.", "cf."]
```

Suppress one rule on one line with a trailing comment:

```latex
\ref{sec:old} % paperlint: disable=no-ref
```

## Editor

The extension in [`editors/vscode`](editors/vscode) runs paperlint on save and shows findings in the Problems list. It works in VS Code and Cursor.

```bash
cd editors/vscode
npm install
npx vsce package
```

Install the `.vsix` that command writes, and set `paperlint.path` to the `paperlint` executable. A root file is chosen from the `paperlint.root` setting, then a `% !TEX root = main.tex` comment, then the active file.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

[MIT](LICENSE).
