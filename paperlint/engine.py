from __future__ import annotations

from pathlib import Path

from paperlint.bib import parse_bibliographies
from paperlint.config import load_config
from paperlint.diagnostic import Diagnostic
from paperlint.rules.bibliography import check_bibliography
from paperlint.rules.citations import check_citations
from paperlint.rules.errors import check_errors
from paperlint.rules.preamble import check_preamble
from paperlint.rules.source_scan import check_source
from paperlint.rules.warnings import check_warnings
from paperlint.tokenize import load_document


def lint_path(path: Path) -> list[Diagnostic]:
    path = path.resolve()
    config = load_config(path.parent)
    document = load_document(path, config)
    entries, bib_suppressions = parse_bibliographies(document.bib_paths)
    for key, rules in bib_suppressions.items():
        document.suppressions.setdefault(key, set()).update(rules)
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(check_errors(document, config))
    diagnostics.extend(check_citations(document, config))
    diagnostics.extend(check_bibliography(document, entries))
    diagnostics.extend(check_warnings(document, config))
    diagnostics.extend(check_source(document))
    kept = _suppress(document, diagnostics)
    kept.extend(check_preamble(document, kept))
    kept = _suppress(document, kept)
    kept.sort(key=lambda item: (str(item.file), item.line, item.col, item.rule_id))
    return kept


def _suppress(document, diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    return [
        item for item in diagnostics
        if item.rule_id not in document.suppressions.get((item.file, item.line), set())
    ]
