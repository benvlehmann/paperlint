from __future__ import annotations

from paperlint.bib import BibEntry, author_names, normalize_value
from paperlint.diagnostic import Diagnostic
from paperlint.document import Document
from paperlint.rules.common import citation_keys, commands

_DUPLICATE_FIELDS = ("eprint", "doi", "url")


def check_bibliography(
    document: Document,
    entries: list[BibEntry],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    known = {entry.key for entry in entries}
    for token in commands(document, {"refcite", "refscite"}):
        for key in citation_keys(token):
            if key not in known:
                diagnostics.append(Diagnostic(
                    token.file, token.line, token.col, "warning",
                    f'key "{key}" was not found in the bibliography',
                    "refcite-missing",
                ))
    diagnostics.extend(_author_counts(entries))
    diagnostics.extend(_duplicates(entries))
    diagnostics.extend(_disallowed_fields(entries))
    return diagnostics


def _author_counts(entries: list[BibEntry]) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for entry in entries:
        raw = entry.fields.get("author")
        if raw is None:
            continue
        names = author_names(raw)
        if len(names) > 10:
            found.append(_field_diag(
                entry, "author",
                f"author list has {len(names)} names; consider `and others` instead",
                "bib-too-many-authors",
            ))
    return found


def _duplicates(entries: list[BibEntry]) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for field_name in _DUPLICATE_FIELDS:
        groups: dict[str, list[BibEntry]] = {}
        for entry in entries:
            if field_name not in entry.fields:
                continue
            normalized = normalize_value(entry.fields[field_name])
            if not normalized:
                continue
            groups.setdefault(normalized, []).append(entry)
        for group in groups.values():
            if len(group) < 2:
                continue
            keys = [entry.key for entry in group]
            for entry in group:
                others = [key for key in keys if key != entry.key]
                found.append(_field_diag(
                    entry, field_name,
                    f"{field_name} is identical to {', '.join(others)}",
                    f"bib-duplicate-{field_name}",
                ))
    return found


def _disallowed_fields(entries: list[BibEntry]) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for entry in entries:
        for name in entry.fields:
            if name == "file":
                found.append(_field_diag(
                    entry, name,
                    'entry contains field "file"',
                    "bib-file-field",
                ))
            elif "mendeley" in name:
                found.append(_field_diag(
                    entry, name,
                    f'entry contains field "{name}"',
                    "bib-mendeley-field",
                ))
    return found


def _field_diag(
    entry: BibEntry,
    field_name: str,
    message: str,
    rule_id: str,
) -> Diagnostic:
    line = entry.field_lines.get(field_name, entry.line)
    return Diagnostic(entry.file, line, 1, "warning", message, rule_id)
