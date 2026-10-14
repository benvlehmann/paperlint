# paperlint

Runs the paperlint command on LaTeX files and shows the results in the Problems list.

Install the Python package from this repository so the `paperlint` command is on your PATH:

```bash
pip install -e /path/to/paperlint
```

If you would rather call the module, set `paperlint.path` to `python3` and `paperlint.args` to `["-m", "paperlint"]`.

The extension lints when you save a `.tex` file. Set `paperlint.run` to `onType` to lint as you edit. A root file is chosen in this order:

1. The `paperlint.root` setting.
2. A `% !TEX root = main.tex` comment in the active file.
3. The active file.

A chapter checked on its own starts with an empty environment stack, so point the linter at the paper's root when the paper is split across files.
