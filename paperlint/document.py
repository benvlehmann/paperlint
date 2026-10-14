from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Token:
    kind: str
    text: str
    file: Path
    line: int
    col: int
    mode: str
    envs: tuple[str, ...]
    sectioning: str | None
    at_sentence_start: bool
    name: str = ""
    optional: tuple[str, ...] = ()
    mandatory: tuple[str, ...] = ()
    preamble: str | None = None
    end_offset: int = -1


@dataclass(frozen=True)
class LineRec:
    file: Path
    number: int
    text: str
    in_display_limit: bool


@dataclass
class Document:
    tokens: list[Token] = field(default_factory=list)
    lines: list[LineRec] = field(default_factory=list)
    suppressions: dict[tuple[Path, int], set[str]] = field(default_factory=dict)
    bib_paths: list[Path] = field(default_factory=list)
    sources: dict[Path, str] = field(default_factory=dict)

    def line_text(self, file: Path, number: int) -> str:
        for rec in self.lines:
            if rec.file == file and rec.number == number:
                return rec.text
        source = self.sources.get(file, "")
        rows = source.splitlines()
        if 1 <= number <= len(rows):
            return rows[number - 1]
        return ""
