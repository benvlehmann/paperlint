from __future__ import annotations

import re

from paperlint.config import Config
from paperlint.diagnostic import Diagnostic
from paperlint.document import Document, Token
from paperlint.rules.common import body_tokens, commands, env_base, lines_for

_SCI_RE = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)[eE][+-]?\d+")
_DISPLAY_ENVS = {"equation", "multline", "align", "gather"}
_RELATIONS = {"=", r"\equiv", r"\approx", r"\propto", r"\simeq"}


def check_warnings(document: Document, config: Config) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_align_single(document))
    diagnostics.extend(_array_piecewise(document))
    diagnostics.extend(_num_scientific(document))
    diagnostics.extend(_table_mathness(document))
    diagnostics.extend(_dashes(document))
    diagnostics.extend(_unary_sim(document))
    diagnostics.extend(_comment_block(document, config))
    diagnostics.extend(_display_blank_line(document))
    diagnostics.extend(_abbrev_space(document, config))
    diagnostics.extend(_lone_qty(document))
    return diagnostics


def _diag(token: Token, message: str, rule_id: str) -> Diagnostic:
    return Diagnostic(token.file, token.line, token.col, "warning", message, rule_id)


def _align_single(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"begin"}):
        if not token.mandatory or env_base(token.mandatory[0]) != "align":
            continue
        body = body_tokens(document, token)
        breaks = [item for item in body if item.kind == "command" and item.name == "\\\\"]
        relations = [
            item for item in body
            if (item.kind == "punct" and item.text == "=")
            or (item.kind == "command" and item.text in _RELATIONS)
        ]
        if len(breaks) == 1 and len(relations) == 1:
            found.append(_diag(token, "use multline for a single split equation", "align-single"))
    return found


def _array_piecewise(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"begin"}):
        if not token.mandatory or token.mandatory[0] != "array":
            continue
        if any(env_base(env) == "table" for env in token.envs):
            continue
        rows = _rows(body_tokens(document, token))
        for row in rows:
            cells = _cells(row)
            if not cells:
                continue
            if _looks_like_condition(cells[-1]):
                found.append(_diag(token, "use cases for a piecewise expression", "array-piecewise"))
                break
    return found


def _rows(tokens: list[Token]) -> list[list[Token]]:
    rows: list[list[Token]] = [[]]
    for token in tokens:
        if token.kind == "command" and token.name == "\\\\":
            rows.append([])
            continue
        rows[-1].append(token)
    return [row for row in rows if row]


def _cells(row: list[Token]) -> list[list[Token]]:
    cells: list[list[Token]] = [[]]
    for token in row:
        if token.kind == "punct" and token.text == "&":
            cells.append([])
            continue
        cells[-1].append(token)
    return cells


def _looks_like_condition(cell: list[Token]) -> bool:
    for token in cell:
        if token.kind == "command" and token.name in {"ll", "gg", "text"}:
            return True
        if token.kind == "word":
            return True
    return False


def _num_scientific(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in document.tokens:
        if token.mode != "text" or token.kind != "number":
            continue
        if _SCI_RE.fullmatch(token.text):
            found.append(_diag(
                token,
                r"use \num for scientific notation",
                "num-scientific",
            ))
    return found


def _table_mathness(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"begin"}):
        if not token.mandatory:
            continue
        env = token.mandatory[0]
        base = env_base(env)
        if base not in {"tabular", "array"}:
            continue
        body = []
        for item in body_tokens(document, token):
            if item.kind in {
                "space", "par", "punct", "nbsp", "control_space",
                "math_shift", "display_open", "display_close",
            }:
                continue
            if item.kind == "command" and item.name in {
                "\\\\", "text", "intertext", "shortintertext", "mbox",
                "textnormal", "textbf", "textit", "textrm",
            }:
                continue
            body.append(item)
        if len(body) < 6:
            continue
        if base == "tabular":
            math = sum(1 for item in body if item.mode != "text")
            if math / len(body) > 0.75:
                found.append(_diag(
                    token,
                    "this tabular is mostly mathematics; consider array",
                    "table-mathness",
                ))
        else:
            words = sum(1 for item in body if item.kind == "word")
            if words / len(body) > 0.5:
                found.append(_diag(
                    token,
                    "this array is mostly words; consider tabular",
                    "table-mathness",
                ))
    return found


def _dashes(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    tokens = document.tokens
    for index, token in enumerate(tokens):
        if token.mode != "text":
            continue
        if (
            token.kind == "number"
            and index + 2 < len(tokens)
            and tokens[index + 1].kind == "punct"
            and tokens[index + 1].text == "-"
            and tokens[index + 1].mode == "text"
            and tokens[index + 2].kind == "number"
            and tokens[index + 2].mode == "text"
        ):
            found.append(_diag(
                tokens[index + 1],
                "use an en dash for a numeric range",
                "dash-range",
            ))
        if token.kind == "punct" and token.text in {"--", "---"}:
            if _space_beside(tokens, index):
                found.append(_diag(
                    token,
                    "do not surround a dash with spaces",
                    "dash-spacing",
                ))
    return found


def _space_beside(tokens: list[Token], index: int) -> bool:
    if index > 0 and tokens[index - 1].kind in {"space", "control_space"}:
        return True
    if index + 1 < len(tokens) and tokens[index + 1].kind in {"space", "control_space"}:
        return True
    return False


def _unary_sim(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    tokens = document.tokens
    for index, token in enumerate(tokens):
        if token.kind != "command" or token.name != "sim" or token.mode == "text":
            continue
        previous = _significant(tokens, index, -1)
        following = _significant(tokens, index, 1)
        if previous is not None and previous.text == "{" and following is not None and following.text == "}":
            continue
        if previous is not None and previous.kind == "command" and previous.name == "mathop":
            continue
        if _has_left_operand(previous):
            continue
        found.append(_diag(
            token,
            r"use {\sim} or \mathop{\sim} for a unary \sim",
            "unary-sim",
        ))
    return found


def _significant(tokens: list[Token], index: int, step: int) -> Token | None:
    cursor = index + step
    while 0 <= cursor < len(tokens):
        if tokens[cursor].kind not in {"space", "control_space", "nbsp", "par"}:
            return tokens[cursor]
        cursor += step
    return None


def _has_left_operand(previous: Token | None) -> bool:
    if previous is None:
        return False
    if previous.kind in {"word", "number"}:
        return True
    if previous.kind == "punct" and previous.text in {")", "]", "}"}:
        return True
    if previous.kind == "command" and previous.name not in {"\\\\", "left"}:
        return True
    return False


def _comment_block(document: Document, config: Config) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    by_file: dict = {}
    for rec in document.lines:
        by_file.setdefault(rec.file, []).append(rec)
    for records in by_file.values():
        records.sort(key=lambda item: item.number)
        run: list = []
        previous_number = None
        for rec in records:
            is_comment = rec.text.lstrip().startswith("%")
            contiguous = previous_number is not None and rec.number == previous_number + 1
            if is_comment and (not run or contiguous):
                run.append(rec)
            else:
                found.extend(_flush_comment_run(run, config.comment_line_threshold))
                run = [rec] if is_comment else []
            previous_number = rec.number
        found.extend(_flush_comment_run(run, config.comment_line_threshold))
    return found


def _flush_comment_run(run: list, threshold: int) -> list[Diagnostic]:
    if len(run) > threshold:
        first = run[0]
        return [Diagnostic(
            first.file, first.number, 1, "warning",
            "use the comment environment instead of a long run of % lines",
            "comment-block",
        )]
    return []


def _display_blank_line(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"begin", "end"}):
        if not token.mandatory or env_base(token.mandatory[0]) not in _DISPLAY_ENVS:
            continue
        lines = lines_for(document, token.file)
        if token.name == "begin":
            previous = lines.get(token.line - 1)
            if previous is not None and previous.strip() == "":
                found.append(_diag(
                    token,
                    "do not put a blank line before display math",
                    "display-blank-line",
                ))
        else:
            following = lines.get(token.line + 1)
            if following is not None and following.strip() == "":
                found.append(_diag(
                    token,
                    "do not put a blank line after display math",
                    "display-blank-line",
                ))
    return found


_LONE_QTY_ENVS = {"equation", "multline", "align", "gather"}
_SPACE_KINDS = {"space", "nbsp", "control_space", "par"}


def _lone_qty(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    tokens = document.tokens
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "math_shift" and token.text in {"$", r"\("}:
            closer = "$" if token.text == "$" else r"\)"
            end = _matching_shift(tokens, index + 1, "math_shift", closer)
            if end is not None:
                _warn_lone_qty(tokens[index + 1:end], found)
                index = end + 1
                continue
        elif token.kind == "display_open":
            closer = "$$" if token.text == "$$" else r"\]"
            end = _matching_shift(tokens, index + 1, "display_close", closer)
            if end is not None:
                _warn_lone_qty(tokens[index + 1:end], found)
                index = end + 1
                continue
        elif (
            token.kind == "command"
            and token.name == "begin"
            and token.mandatory
            and env_base(token.mandatory[0]) in _LONE_QTY_ENVS
        ):
            _warn_lone_qty(body_tokens(document, token), found)
        index += 1
    return found


def _matching_shift(tokens: list[Token], start: int, kind: str, text: str) -> int | None:
    for index in range(start, len(tokens)):
        if tokens[index].kind == kind and tokens[index].text == text:
            return index
    return None


def _warn_lone_qty(tokens: list[Token], found: list[Diagnostic]) -> None:
    significant = [token for token in tokens if token.kind not in _SPACE_KINDS]
    if len(significant) == 1 and significant[0].kind == "command" and significant[0].name == "qty":
        found.append(_diag(
            significant[0],
            r"do not wrap a lone \qty in math mode",
            "qty-math",
        ))


def _abbrev_space(document: Document, config: Config) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    tokens = document.tokens
    for index, token in enumerate(tokens):
        if token.kind != "word" or token.mode != "text":
            continue
        if token.text.casefold() not in config.abbreviations:
            continue
        if index + 1 < len(tokens) and tokens[index + 1].kind == "space":
            found.append(_diag(
                token,
                r"follow an abbreviation with \  or \@.",
                "abbrev-space",
            ))
    return found
