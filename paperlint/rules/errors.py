from __future__ import annotations

from paperlint.config import Config
from paperlint.diagnostic import Diagnostic
from paperlint.document import Document, Token
from paperlint.rules.common import (
    ENV_MACRO_RE,
    commands,
    env_base,
    line_is_only_env_command,
)


def check_errors(document: Document, config: Config) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_labels(document, config))
    diagnostics.extend(_refs(document))
    diagnostics.extend(_cref_sentence_case(document))
    diagnostics.extend(_cref_combine(document))
    diagnostics.extend(_display_delims(document))
    diagnostics.extend(_eqnarray(document))
    diagnostics.extend(_figure_placement(document))
    diagnostics.extend(_booktabs(document))
    diagnostics.extend(_legacy_font(document))
    diagnostics.extend(_mathrm_text(document))
    diagnostics.extend(_env_own_line(document))
    diagnostics.extend(_env_macros(document))
    diagnostics.extend(_tilde_math(document))
    diagnostics.extend(_display_line_length(document))
    return diagnostics


def _diag(token: Token, severity: str, message: str, rule_id: str) -> Diagnostic:
    return Diagnostic(token.file, token.line, token.col, severity, message, rule_id)


def _expected_prefix(token: Token, config: Config) -> str | None:
    for env in reversed(token.envs):
        base = env_base(env)
        for prefix, names in config.label_envs.items():
            if base in names:
                return prefix
    if token.sectioning:
        return "sec:"
    return None


def _labels(document: Document, config: Config) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    prefixes = ", ".join(config.label_prefixes)
    for token in commands(document, {"label"}):
        if not token.mandatory:
            continue
        key = token.mandatory[0]
        if any(char.isspace() for char in key):
            found.append(_diag(
                token, "error",
                f'label "{key}" contains a space',
                "label-key",
            ))
        expected = _expected_prefix(token, config)
        if expected is not None:
            if not key.startswith(expected):
                found.append(_diag(
                    token, "error",
                    f'label "{key}" must use prefix "{expected}"',
                    "label-key",
                ))
        elif not any(key.startswith(prefix) for prefix in config.label_prefixes):
            found.append(_diag(
                token, "error",
                f'label "{key}" must begin with {prefixes}',
                "label-key",
            ))
    return found


def _refs(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"ref", "eqref"}):
        replacement = r"\cref"
        found.append(_diag(
            token, "error",
            f"use {replacement} instead of \\{token.name}",
            "no-ref",
        ))
    return found


def _cref_sentence_case(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"cref"}):
        if token.mode == "text" and token.at_sentence_start:
            found.append(_diag(
                token, "error",
                r"use \Cref at the start of a sentence",
                "cref-sentence-case",
            ))
    return found


def _cref_combine(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    cites = [
        token for token in commands(document, {"cref"})
        if token.mode == "text" and _all_eq_keys(token)
    ]
    index = {id(token): position for position, token in enumerate(document.tokens)}
    used: set[int] = set()
    for left, right in zip(cites, cites[1:]):
        if id(left) in used or id(right) in used:
            continue
        between = document.tokens[index[id(left)] + 1:index[id(right)]]
        if not _joined_by_and(between):
            continue
        keys = _keys(left) + _keys(right)
        used.add(id(left))
        used.add(id(right))
        found.append(_diag(
            left, "error",
            r"combine equation references: \cref{" + ",".join(keys) + "}",
            "cref-combine",
        ))
    return found


def _all_eq_keys(token: Token) -> bool:
    keys = _keys(token)
    return bool(keys) and all(key.startswith("eq:") for key in keys)


def _keys(token: Token) -> list[str]:
    if not token.mandatory:
        return []
    return [part.strip() for part in token.mandatory[0].split(",") if part.strip()]


def _joined_by_and(tokens: list[Token]) -> bool:
    words = [token for token in tokens if token.kind == "word"]
    if len(words) != 1 or words[0].text.casefold() != "and":
        return False
    for token in tokens:
        if token.kind == "word":
            continue
        if token.kind in {"space", "nbsp", "control_space", "par", "punct"}:
            continue
        return False
    return True


def _display_delims(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in document.tokens:
        if token.kind != "display_open":
            continue
        shown = "$$" if token.text == "$$" else r"\["
        found.append(_diag(
            token, "error",
            f"use the equation environment instead of {shown}",
            "no-display-delims",
        ))
    return found


def _eqnarray(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"begin"}):
        if token.mandatory and env_base(token.mandatory[0]) == "eqnarray":
            found.append(_diag(
                token, "error",
                "use equation, multline, or align instead of eqnarray",
                "no-eqnarray",
            ))
    return found


def _figure_placement(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"begin"}):
        if not token.mandatory:
            continue
        if token.mandatory[0] in {"figure", "figure*"} and token.optional:
            found.append(_diag(
                token, "error",
                "do not pass a placement argument to figure",
                "figure-placement",
            ))
    return found


def _booktabs(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"begin"}):
        if token.preamble is not None and "|" in token.preamble:
            found.append(_diag(
                token, "error",
                "use booktabs rules instead of vertical rules",
                "booktabs",
            ))
    for token in commands(document, {"hline", "cline", "vline"}):
        found.append(_diag(
            token, "error",
            f"use booktabs rules instead of \\{token.name}",
            "booktabs",
        ))
    return found


def _legacy_font(document: Document) -> list[Diagnostic]:
    replacements = {
        "bf": r"\textbf",
        "it": r"\textit",
        "rm": r"\mathrm",
        "color": r"\textcolor",
    }
    found: list[Diagnostic] = []
    for token in commands(document, set(replacements)):
        found.append(_diag(
            token, "error",
            f"use {replacements[token.name]} instead of \\{token.name}",
            "legacy-font",
        ))
    return found


def _mathrm_text(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"mathrm"}):
        if not token.mandatory:
            continue
        argument = token.mandatory[0]
        if any(char.isspace() for char in argument) or any(
            dash in argument for dash in ("-", "–", "—")
        ):
            found.append(_diag(
                token, "error",
                r"use \textnormal for text with spaces or dashes",
                "mathrm-text",
            ))
    return found


def _env_own_line(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in commands(document, {"begin", "end"}):
        line = document.line_text(token.file, token.line)
        if line and not line_is_only_env_command(line):
            found.append(_diag(
                token, "error",
                f"\\{token.name} must occupy its own line",
                "env-own-line",
            ))
    return found


def _env_macros(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    names = {
        "newcommand", "newcommand*",
        "renewcommand", "renewcommand*",
        "newenvironment", "newenvironment*",
        "renewenvironment", "renewenvironment*",
    }
    for token in commands(document, names):
        for body in token.mandatory:
            if ENV_MACRO_RE.search(body):
                found.append(_diag(
                    token, "error",
                    "do not hide \\begin or \\end inside a macro",
                    "no-env-macro",
                ))
                break
    return found


def _tilde_math(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for token in document.tokens:
        if token.kind == "nbsp" and token.mode != "text":
            found.append(_diag(
                token, "error",
                "use \\,, \\;, \\quad, \\qquad, or \\hspace in math mode",
                "no-tilde-math",
            ))
    return found


def _display_line_length(document: Document) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for rec in document.lines:
        if rec.in_display_limit and len(rec.text) > 80:
            found.append(Diagnostic(
                rec.file, rec.number, 1, "error",
                "display-math source lines must be at most 80 characters",
                "display-line-length",
            ))
    return found
