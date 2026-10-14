from __future__ import annotations

import re

from paperlint.diagnostic import Diagnostic
from paperlint.document import Document

_SKIP_ENVS = ("verbatim", "Verbatim", "lstlisting", "minted", "comment")
_UNITS = (
    "nm", "mm", "cm", "km",
    "pc", "AU", "eV", "kg", "yr", "Hz",
)
_UNIT_RE = re.compile(
    "(?<!-)"
    "(?:"
    + "|".join(re.escape(unit) for unit in sorted(_UNITS, key=len, reverse=True))
    + r")(?![A-Za-z-])"
)
_MU_M_RE = re.compile(r"\\mu(?:\s+|\\,\s*)?m(?![A-Za-z-])")
_SOLAR_RE = re.compile(r"M_\{\\odot\}|M_\\odot")
_POWER_RE = re.compile(
    r"(?:(?P<mant>\d+(?:\.\d+)?)[ \t\n]*(?:\\times|×)[ \t\n]*)?"
    r"(?<!\d)10\^(?:\{(?P<braced>[+-]?\d+)\}|(?P<bare>[+-]?\d+))"
)


def check_source(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for file, text in document.sources.items():
        masked, arguments = _mask(text)
        found.extend(_units(file, text, masked, arguments))
        found.extend(_powers(file, text, masked))
    return found


def _units(file, text: str, masked: str, arguments: list[tuple[int, int]]) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for pattern in (_SOLAR_RE, _MU_M_RE, _UNIT_RE):
        for match in pattern.finditer(masked):
            if _tex_length_cm(text, match.start(), match.end(), arguments):
                continue
            line, col = _linecol(text, match.start())
            found.append(Diagnostic(
                file, line, col, "warning",
                rf"use \qty for {match.group(0)}",
                "unit-bare",
            ))
    return found


def _powers(file, text: str, masked: str) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for match in _POWER_RE.finditer(masked):
        exponent = match.group("braced") or match.group("bare")
        if exponent is None:
            continue
        exponent = exponent[1:] if exponent.startswith("+") else exponent
        mantissa = match.group("mant")
        replacement = rf"\num{{{mantissa}e{exponent}}}" if mantissa else rf"\num{{e{exponent}}}"
        original = match.group(0).replace("\n", " ")
        line, col = _linecol(text, match.start())
        found.append(Diagnostic(
            file, line, col, "warning",
            f"use {replacement} rather than {original}",
            "num-power",
        ))
    return found


def _linecol(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    last_nl = text.rfind("\n", 0, index)
    return line, index - last_nl


def _tex_length_cm(text: str, start: int, end: int, arguments: list[tuple[int, int]]) -> bool:
    if text[start:end] != "cm":
        return False
    if not any(left <= start < right for left, right in arguments):
        return False
    cursor = start - 1
    if cursor < 0 or not text[cursor].isdigit():
        return False
    while cursor >= 0 and text[cursor].isdigit():
        cursor -= 1
    if cursor >= 0 and text[cursor] == ".":
        cursor -= 1
        while cursor >= 0 and text[cursor].isdigit():
            cursor -= 1
    return True


def _mask(text: str) -> tuple[str, list[tuple[int, int]]]:
    chars = list(text)
    length = len(text)
    index = 0
    arguments: list[tuple[int, int]] = []

    def blank(start: int, end: int) -> None:
        for cursor in range(start, min(end, length)):
            if chars[cursor] != "\n":
                chars[cursor] = " "

    while index < length:
        char = text[index]
        if char == "%":
            newline = text.find("\n", index)
            end = length if newline < 0 else newline
            blank(index, end)
            index = end
            continue
        if char != "\\":
            index += 1
            continue
        if text.startswith(r"\verb", index) and not _command_continues(text, index, "verb"):
            end = _skip_verb(text, index)
            blank(index, end)
            index = end
            continue
        if text.startswith(r"\qty", index) and not _command_continues(text, index, "qty"):
            end = _skip_qty(text, index)
            blank(index, end)
            index = end
            continue
        if text.startswith(r"\DeclareSIUnit", index) and not _command_continues(text, index, "DeclareSIUnit"):
            end = _skip_qty(text, index)
            blank(index, end)
            index = end
            continue
        if text.startswith(r"\num", index) and not _command_continues(text, index, "num"):
            end = _skip_num(text, index)
            blank(index, end)
            index = end
            continue
        cite = _cite_command(text, index)
        if cite is not None:
            _blank_cite_keys(text, index, blank)
            index = cite
            _note_arguments(text, index, arguments)
            continue
        begin = _begin_env(text, index)
        if begin is not None:
            env, name_end = begin
            if env in _SKIP_ENVS:
                closer = "\\end{" + env + "}"
                found = text.find(closer, name_end)
                end = length if found < 0 else found + len(closer)
                blank(index, end)
                index = end
                continue
        index = _skip_control(text, index)
        _note_arguments(text, index, arguments)
    return "".join(chars), arguments


def _note_arguments(text: str, index: int, arguments: list[tuple[int, int]]) -> None:
    cursor = index
    while True:
        nxt = _skip_space(text, cursor)
        if nxt >= len(text) or text[nxt] not in "{[":
            return
        close = "}" if text[nxt] == "{" else "]"
        end = _skip_group(text, nxt, text[nxt], close)
        if end <= nxt:
            return
        arguments.append((nxt + 1, end - 1))
        cursor = end


def _command_continues(text: str, index: int, name: str) -> bool:
    after = index + 1 + len(name)
    return after < len(text) and text[after].isalpha()


def _skip_control(text: str, index: int) -> int:
    cursor = index + 1
    if cursor >= len(text):
        return cursor
    if text[cursor].isalpha():
        while cursor < len(text) and text[cursor].isalpha():
            cursor += 1
        if cursor < len(text) and text[cursor] == "*":
            cursor += 1
        return cursor
    return cursor + 1


def _skip_verb(text: str, index: int) -> int:
    cursor = index + len(r"\verb")
    if cursor < len(text) and text[cursor] == "*":
        cursor += 1
    if cursor >= len(text) or text[cursor].isspace():
        return cursor
    delim = text[cursor]
    cursor += 1
    while cursor < len(text) and text[cursor] != delim:
        cursor += 1
    if cursor < len(text):
        cursor += 1
    return cursor


def _skip_qty(text: str, index: int) -> int:
    cursor = _skip_control(text, index)
    cursor = _skip_space(text, cursor)
    if cursor < len(text) and text[cursor] == "[":
        cursor = _skip_group(text, cursor, "[", "]")
        cursor = _skip_space(text, cursor)
    for _ in range(2):
        cursor = _skip_space(text, cursor)
        if cursor >= len(text) or text[cursor] != "{":
            break
        cursor = _skip_group(text, cursor, "{", "}")
    return cursor


def _cite_command(text: str, index: int) -> int | None:
    for name in ("refscite", "refcite", "cite"):
        if text.startswith("\\" + name, index) and not _command_continues(text, index, name):
            return _skip_control(text, index)
    return None


def _blank_cite_keys(text: str, index: int, blank) -> None:
    cursor = _skip_control(text, index)
    for _ in range(2):
        nxt = _skip_space(text, cursor)
        if nxt < len(text) and text[nxt] == "[":
            cursor = _skip_group(text, nxt, "[", "]")
        else:
            break
    nxt = _skip_space(text, cursor)
    if nxt < len(text) and text[nxt] == "{":
        blank(nxt, _skip_group(text, nxt, "{", "}"))


def _skip_num(text: str, index: int) -> int:
    cursor = _skip_control(text, index)
    cursor = _skip_space(text, cursor)
    if cursor < len(text) and text[cursor] == "[":
        cursor = _skip_group(text, cursor, "[", "]")
        cursor = _skip_space(text, cursor)
    if cursor < len(text) and text[cursor] == "{":
        cursor = _skip_group(text, cursor, "{", "}")
    return cursor


def _skip_space(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\n":
        index += 1
    return index


def _skip_group(text: str, index: int, open_char: str, close_char: str) -> int:
    depth = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "%":
            newline = text.find("\n", index)
            index = len(text) if newline < 0 else newline
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return index


def _begin_env(text: str, index: int) -> tuple[str, int] | None:
    if not text.startswith(r"\begin{", index):
        return None
    start = index + len(r"\begin{")
    end = text.find("}", start)
    if end < 0:
        return None
    return text[start:end], end + 1
