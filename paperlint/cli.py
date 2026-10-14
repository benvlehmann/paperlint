from __future__ import annotations

import sys
from pathlib import Path

from paperlint.engine import lint_path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: paperlint FILE", file=sys.stderr)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"paperlint: {path} is not a file", file=sys.stderr)
        return 2
    diagnostics = lint_path(path)
    for diagnostic in diagnostics:
        print(diagnostic.format())
    if any(item.severity == "error" for item in diagnostics):
        return 1
    return 0
