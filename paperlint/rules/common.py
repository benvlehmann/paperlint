from __future__ import annotations

from pathlib import Path

from paperlint.document import Document, Token


def commands(document: Document, names: set[str] | None = None) -> list[Token]:
    found: list[Token] = []
    for token in document.tokens:
        if token.kind != "command":
            continue
        if names is not None and token.name not in names:
            continue
        found.append(token)
    return found


def split_keys(argument: str) -> list[str]:
    return [part.strip() for part in argument.split(",") if part.strip()]


def citation_keys(token: Token) -> list[str]:
    if not token.mandatory:
        return []
    return split_keys(token.mandatory[0])


def has_possessive(document: Document, token: Token) -> bool:
    if token.end_offset < 0:
        return False
    source = document.sources.get(token.file, "")
    return source.startswith("'s", token.end_offset)


def macro_for(keys: list[str]) -> str:
    return r"\refscite" if len(keys) > 1 else r"\refcite"


def strip_comment(line: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(line):
        if line[index] == "\\":
            out.append(line[index:index + 2])
            index += 2
            continue
        if line[index] == "%":
            break
        out.append(line[index])
        index += 1
    return "".join(out)


def skip_balanced(text: str, index: int, open_char: str, close_char: str) -> int:
    if index >= len(text) or text[index] != open_char:
        return -1
    depth = 0
    i = index
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def line_is_only_env_command(line: str) -> bool:
    stripped = strip_comment(line).strip()
    if stripped.startswith("\\begin{"):
        index = skip_balanced(stripped, 6, "{", "}")
        if index < 0:
            return False
        extras = 0
        while extras < 4:
            while index < len(stripped) and stripped[index] in " \t":
                index += 1
            if index >= len(stripped):
                return True
            if stripped[index] == "[":
                index = skip_balanced(stripped, index, "[", "]")
                if index < 0:
                    return False
                continue
            if stripped[index] == "{":
                index = skip_balanced(stripped, index, "{", "}")
                if index < 0:
                    return False
                extras += 1
                continue
            return _only_ignorespaces(stripped[index:])
        return _only_ignorespaces(stripped[index:])
    if stripped.startswith("\\end{"):
        index = skip_balanced(stripped, 4, "{", "}")
        if index < 0:
            return False
        return stripped[index:].strip() == ""
    return False


def _only_ignorespaces(rest: str) -> bool:
    return rest.strip() in {"", "\\ignorespaces"}


def env_base(name: str) -> str:
    return name[:-1] if name.endswith("*") else name


def body_tokens(document: Document, begin: Token) -> list[Token]:
    if not begin.mandatory:
        return []
    start = next(
        (index for index, token in enumerate(document.tokens) if token is begin),
        -1,
    )
    if start < 0:
        return []
    env = begin.mandatory[0]
    depth = 0
    body: list[Token] = []
    for token in document.tokens[start:]:
        if token.kind == "command" and token.name == "begin" and token.mandatory:
            if token.mandatory[0] == env:
                depth += 1
                if depth == 1:
                    continue
            body.append(token)
            continue
        if token.kind == "command" and token.name == "end" and token.mandatory:
            if token.mandatory[0] == env:
                depth -= 1
                if depth == 0:
                    break
        body.append(token)
    return body


def lines_for(document: Document, file: Path) -> dict[int, str]:
    return {
        rec.number: rec.text
        for rec in document.lines
        if rec.file == file
    }
