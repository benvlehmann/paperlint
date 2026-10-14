from __future__ import annotations

import re
from pathlib import Path

from paperlint.diagnostic import Diagnostic
from paperlint.document import Document
from paperlint.rules.common import strip_comment

_DEFINE_REF = {
    "refcite": r"\newcommand{\refcite}[1]{Ref.~\cite{#1}}",
    "refscite": r"\newcommand{\refscite}[1]{Refs.~\cite{#1}}",
}
_SUGGESTION_RULES = {"cite-sentence-role", "cite-plural", "cite-possessive"}
_SIUNITX_RULES = {"unit-bare", "num-power", "num-scientific"}
_CUSTOM_SI_UNITS = {
    "yr": r"\DeclareSIUnit{\year}{yr}",
    "pc": r"\DeclareSIUnit{\parsec}{pc}",
    "AU": r"\DeclareSIUnit{\au}{AU}",
}
_CUSTOM_SI_COMMANDS = {"yr": "year", "pc": "parsec", "AU": "au"}
_PACKAGE_RE = re.compile(
    r"\\(?:usepackage|RequirePackage)\*?\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}"
)


def check_preamble(document: Document, diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    text = _uncommented(document)
    defined = _defined_commands(text)
    packages = _loaded_packages(text)
    file, line = _anchor(document)
    found: list[Diagnostic] = []
    for name in ("refscite", "refcite"):
        if name in defined or not _suggests(diagnostics, name):
            continue
        found.append(_hint(
            file, line,
            f"add {_DEFINE_REF[name]} to the preamble",
            f"define-{name}",
        ))
    if any(item.rule_id == "booktabs" for item in diagnostics) and "booktabs" not in packages:
        found.append(_hint(file, line, r"add \usepackage{booktabs} to the preamble", "usepackage-booktabs"))
    needs_siunitx = any(item.rule_id in _SIUNITX_RULES for item in diagnostics)
    if needs_siunitx and "siunitx" not in packages:
        found.append(_hint(file, line, r"add \usepackage{siunitx} to the preamble", "usepackage-siunitx"))
    elif "siunitx" in packages:
        found.extend(_declare_si_units(document, text, diagnostics))
    return found


def _declare_si_units(document: Document, text: str, diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    used = set()
    for item in diagnostics:
        if item.rule_id != "unit-bare":
            continue
        unit = item.message.removeprefix(r"use \qty for ")
        if unit in _CUSTOM_SI_UNITS:
            used.add(unit)
    anchor = _siunitx_line(document)
    if anchor is None:
        return []
    file, line = anchor
    found: list[Diagnostic] = []
    for unit in ("yr", "pc", "AU"):
        if unit not in used or _si_unit_declared(text, _CUSTOM_SI_COMMANDS[unit]):
            continue
        found.append(_hint(
            file, line,
            f"add {_CUSTOM_SI_UNITS[unit]} to the preamble",
            "declare-si-unit",
        ))
    return found


def _si_unit_declared(text: str, command: str) -> bool:
    pattern = (
        r"\\DeclareSIUnit\*?\s*(?:\[[^\]]*\])?\s*\{\s*\\"
        + command
        + r"\s*\}"
    )
    return re.search(pattern, text) is not None


def _siunitx_line(document: Document) -> tuple[Path, int] | None:
    for file, source in document.sources.items():
        for number, line in enumerate(source.splitlines(), start=1):
            match = _PACKAGE_RE.search(strip_comment(line))
            if match is None:
                continue
            names = {name.strip() for name in match.group(1).split(",")}
            if "siunitx" in names:
                return file, number + 1
    return None


def _suggests(diagnostics: list[Diagnostic], name: str) -> bool:
    needle = "\\" + name
    for item in diagnostics:
        if item.rule_id not in _SUGGESTION_RULES:
            continue
        if name == "refcite" and r"\refscite" in item.message:
            continue
        if needle in item.message:
            return True
    return False


def _defined_commands(text: str) -> set[str]:
    defined: set[str] = set()
    pattern = re.compile(
        r"\\(?:newcommand|renewcommand|providecommand|DeclareRobustCommand)\*?"
        r"\s*\{\s*\\(refcite|refscite)\s*\}"
        r"|\\def\s*\\(refcite|refscite)(?![A-Za-z])"
    )
    for match in pattern.finditer(text):
        defined.add(match.group(1) or match.group(2))
    return defined


def _loaded_packages(text: str) -> set[str]:
    names: set[str] = set()
    for match in _PACKAGE_RE.finditer(text):
        for name in match.group(1).split(","):
            cleaned = name.strip()
            if cleaned:
                names.add(cleaned)
    return names


def _uncommented(document: Document) -> str:
    parts: list[str] = []
    for text in document.sources.values():
        lines = []
        for line in text.splitlines(keepends=True):
            newline = "\n" if line.endswith("\n") else ""
            lines.append(strip_comment(line.removesuffix("\n")) + newline)
        parts.append("".join(lines))
    return "\n".join(parts)


def _anchor(document: Document) -> tuple[Path, int]:
    for token in document.tokens:
        if token.kind == "command" and token.name == "documentclass":
            return token.file, token.line
    if document.sources:
        return next(iter(document.sources)), 1
    return Path("main.tex"), 1


def _hint(file: Path, line: int, message: str, rule_id: str) -> Diagnostic:
    return Diagnostic(file, line, 1, "warning", message, rule_id)
