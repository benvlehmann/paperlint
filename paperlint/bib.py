from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from paperlint.tokenize import DISABLE_RE, line_is_style_ok

_AND_RE = re.compile(r"\s+and\s+", re.IGNORECASE)


@dataclass
class BibEntry:
    file: Path
    line: int
    key: str
    entry_type: str
    fields: dict[str, str] = field(default_factory=dict)
    field_lines: dict[str, int] = field(default_factory=dict)


def parse_bibliographies(
    paths: list[Path],
) -> tuple[list[BibEntry], dict[tuple[Path, int], set[str]], set[tuple[Path, int]]]:
    entries: list[BibEntry] = []
    suppressions: dict[tuple[Path, int], set[str]] = {}
    exempt_lines: set[tuple[Path, int]] = set()
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        found, suppressed, exempt = _parse_file(resolved)
        entries.extend(found)
        exempt_lines.update(exempt)
        for key, rules in suppressed.items():
            suppressions.setdefault(key, set()).update(rules)
    return entries, suppressions, exempt_lines


def normalize_value(raw: str) -> str:
    text = raw.strip()
    changed = True
    while changed and len(text) >= 2 and text[0] == "{" and text[-1] == "}":
        if not _outer_braces_wrap(text):
            break
        text = text[1:-1].strip()
        changed = True
        if text == raw.strip():
            break
    text = re.sub(r"\s+", " ", text).strip()
    return text


def author_names(raw: str) -> list[str]:
    names: list[str] = []
    buffer: list[str] = []
    depth = 0
    i = 0
    while i < len(raw):
        char = raw[i]
        if char == "{":
            depth += 1
            buffer.append(char)
            i += 1
            continue
        if char == "}":
            depth = max(0, depth - 1)
            buffer.append(char)
            i += 1
            continue
        if depth == 0:
            match = _AND_RE.match(raw, i)
            if match:
                names.append("".join(buffer).strip())
                buffer = []
                i = match.end()
                continue
        buffer.append(char)
        i += 1
    tail = "".join(buffer).strip()
    if tail:
        names.append(tail)
    return [name for name in names if name and name.casefold() != "others"]


def _outer_braces_wrap(text: str) -> bool:
    depth = 0
    for index, char in enumerate(text):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index == len(text) - 1
            if depth < 0:
                return False
    return False


class _BibScanner:
    def __init__(self, path: Path, text: str) -> None:
        self.path = path
        self.s = text
        self.i = 0
        self.line = 1
        self.suppressions: dict[tuple[Path, int], set[str]] = {}

    def parse(self) -> list[BibEntry]:
        entries: list[BibEntry] = []
        while self.i < len(self.s):
            char = self.peek()
            if char in " \t\r":
                self.advance()
                continue
            if char == "\n":
                self.advance()
                continue
            if char == "%":
                self._comment()
                continue
            if char == "@":
                entry = self._entry()
                if entry is not None:
                    entries.append(entry)
                continue
            self.advance()
        return entries

    def peek(self) -> str:
        if self.i >= len(self.s):
            return ""
        return self.s[self.i]

    def advance(self) -> None:
        if self.i >= len(self.s):
            return
        if self.s[self.i] == "\n":
            self.line += 1
        self.i += 1

    def _comment(self) -> None:
        start_line = self.line
        start = self.i
        while self.peek() not in {"", "\n"}:
            self.advance()
        match = DISABLE_RE.search(self.s[start:self.i])
        if match:
            ids = {part.strip() for part in match.group(1).split(",") if part.strip()}
            self.suppressions.setdefault((self.path, start_line), set()).update(ids)
        if self.peek() == "\n":
            self.advance()

    def _entry(self) -> BibEntry | None:
        entry_line = self.line
        self.advance()  # @
        type_start = self.i
        while self.peek().isalpha():
            self.advance()
        entry_type = self.s[type_start:self.i].casefold()
        self._skip_ws()
        if entry_type in {"string", "preamble"}:
            if self.peek() == "{":
                self._skip_balanced("{", "}")
            elif self.peek() == "(":
                self._skip_balanced("(", ")")
            return None
        if entry_type == "comment":
            if self.peek() == "{":
                self._skip_balanced("{", "}")
            else:
                while self.peek() not in {"", "\n"}:
                    self.advance()
            return None
        if self.peek() == "(":
            closer = ")"
            self.advance()
        elif self.peek() == "{":
            closer = "}"
            self.advance()
        else:
            return None
        key = self._read_key()
        entry = BibEntry(self.path, entry_line, key, entry_type)
        if self.peek() == ",":
            self.advance()
        while self.i < len(self.s) and self.peek() != closer:
            self._skip_ws()
            if self.peek() in {"", closer}:
                break
            if self.peek() == ",":
                self.advance()
                continue
            field_line = self.line
            name = self._read_name()
            self._skip_ws()
            if self.peek() != "=":
                break
            self.advance()
            value = self._read_value()
            if name:
                lowered = name.casefold()
                entry.fields[lowered] = value
                entry.field_lines[lowered] = field_line
            self._skip_ws()
            if self.peek() == ",":
                self.advance()
        if self.peek() == closer:
            self.advance()
        return entry

    def _read_key(self) -> str:
        self._skip_ws()
        chars: list[str] = []
        while self.peek() not in {"", ",", "{", "}", "(", ")", " ", "\t", "\n", "%"}:
            chars.append(self.peek())
            self.advance()
        return "".join(chars).strip()

    def _read_name(self) -> str:
        chars: list[str] = []
        while self.peek() not in {"", "=", ",", "{", "}", "(", ")", " ", "\t", "\n", "%"}:
            chars.append(self.peek())
            self.advance()
        return "".join(chars).strip()

    def _read_value(self) -> str:
        parts: list[str] = []
        while True:
            self._skip_ws()
            char = self.peek()
            if char == "{":
                parts.append(self._read_braced())
            elif char == '"':
                parts.append(self._read_quoted())
            else:
                parts.append(self._read_bare())
            self._skip_ws()
            if self.peek() == "#":
                self.advance()
                continue
            break
        return "".join(parts)

    def _read_braced(self) -> str:
        self.advance()
        start = self.i
        depth = 1
        while self.i < len(self.s) and depth:
            char = self.peek()
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    inner = self.s[start:self.i]
                    self.advance()
                    return inner
            self.advance()
        return self.s[start:self.i]

    def _read_quoted(self) -> str:
        self.advance()
        chars: list[str] = []
        while self.peek() not in {"", '"'} :
            if self.peek() == "\\":
                self.advance()
                if self.peek() != "":
                    chars.append(self.peek())
                    self.advance()
                continue
            chars.append(self.peek())
            self.advance()
        if self.peek() == '"':
            self.advance()
        return "".join(chars)

    def _read_bare(self) -> str:
        chars: list[str] = []
        while self.peek() not in {"", ",", "#", "{", "}", "(", ")", "%", "\n"}:
            if self.peek() in (" ", "\t"):
                break
            chars.append(self.peek())
            self.advance()
        return "".join(chars)

    def _skip_ws(self) -> None:
        while self.i < len(self.s):
            if self.peek() in (" ", "\t", "\r", "\n"):
                self.advance()
                continue
            if self.peek() == "%":
                self._comment()
                continue
            return

    def _skip_balanced(self, open_char: str, close_char: str) -> None:
        if self.peek() != open_char:
            return
        self.advance()
        depth = 1
        while self.i < len(self.s) and depth:
            char = self.peek()
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
            self.advance()


def _parse_file(
    path: Path,
) -> tuple[list[BibEntry], dict[tuple[Path, int], set[str]], set[tuple[Path, int]]]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    scanner = _BibScanner(path, text)
    exempt = {
        (path, number)
        for number, line in enumerate(text.splitlines(), start=1)
        if line_is_style_ok(line)
    }
    return scanner.parse(), scanner.suppressions, exempt
