from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Diagnostic:
    file: Path
    line: int
    col: int
    severity: str
    message: str
    rule_id: str

    def format(self) -> str:
        file = _display_path(self.file)
        return (
            f"{file}:{self.line}:{self.col}: {self.severity}: "
            f"{self.message} [{self.rule_id}]"
        )


def _display_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve())
    except ValueError:
        return resolved
