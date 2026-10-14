from __future__ import annotations

from paperlint.config import Config
from paperlint.diagnostic import Diagnostic
from paperlint.document import Document, Token
from paperlint.rules.common import (
    citation_keys,
    commands,
    env_base,
    has_possessive,
    macro_for,
    strip_comment,
)

_SKIP_BEFORE_WORD = {"space", "nbsp", "control_space", "punct"}


def check_citations(document: Document, config: Config) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    positions = {id(token): index for index, token in enumerate(document.tokens)}
    refcites = [
        token for token in commands(document, {"refcite"})
        if token.mode == "text"
    ]
    consumed_pairs: set[int] = set()

    for token in commands(document, {"cite", "refcite", "refscite"}):
        keys = citation_keys(token)
        if not keys:
            diagnostics.append(_diag(token, "citation has no key", "cite-empty"))
            continue
        possessive = has_possessive(document, token)
        if possessive:
            diagnostics.append(_possessive(token, keys))
        if token.name == "cite":
            if possessive or token.mode != "text":
                continue
            diagnostics.extend(_cite_role(document, config, token, positions, keys))
            continue
        if len(keys) > 1 and token.name == "refcite":
            diagnostics.append(_diag(
                token,
                f"use \\refscite{{{','.join(keys)}}}",
                "cite-plural",
            ))
        elif len(keys) == 1 and token.name == "refscite":
            diagnostics.append(_diag(
                token,
                f"use \\refcite{{{keys[0]}}}",
                "cite-plural",
            ))

    for left, right in zip(refcites, refcites[1:]):
        if id(left) in consumed_pairs or id(right) in consumed_pairs:
            continue
        if len(citation_keys(left)) != 1 or len(citation_keys(right)) != 1:
            continue
        between = document.tokens[positions[id(left)] + 1:positions[id(right)]]
        if not _joined_by_and(between):
            continue
        keys = citation_keys(left) + citation_keys(right)
        consumed_pairs.add(id(left))
        consumed_pairs.add(id(right))
        diagnostics.append(_diag(
            left,
            f"use \\refscite{{{','.join(keys)}}}",
            "cite-plural",
        ))
    return diagnostics


def _cite_role(
    document: Document,
    config: Config,
    token: Token,
    positions: dict[int, int],
    keys: list[str],
) -> list[Diagnostic]:
    nearest = _nearest_word(document.tokens, positions[id(token)])
    folded = nearest.casefold() if nearest is not None else None
    breakable = _breakable_before(document.tokens, positions[id(token)])
    excluded = folded in config.exclusions if folded is not None else False
    trigger = folded in config.triggers if folded is not None else False
    macro = macro_for(keys)
    if _in_tabular_or_array(token) or _tied_before_environment(document, token, positions):
        return []
    if excluded:
        if breakable:
            return [_diag(
                token,
                "use ~ before \\cite",
                "cite-parenthetical-tie",
                severity="warning",
            )]
        return []
    if token.at_sentence_start or trigger or breakable:
        if trigger and nearest is not None:
            message = f'citation is the object of "{nearest}"; use {macro}'
        else:
            message = f"citation is used as a word in the sentence; use {macro}"
        return [_diag(token, message, "cite-sentence-role", severity="warning")]
    return []


def _possessive(token: Token, keys: list[str]) -> Diagnostic:
    rendered = ",".join(keys) if keys else ""
    macro = macro_for(keys)
    return _diag(
        token,
        f"rephrase the possessive, typically “of {macro}{{{rendered}}}”",
        "cite-possessive",
        severity="warning",
    )


def _nearest_word(tokens: list[Token], index: int) -> str | None:
    cursor = index - 1
    while cursor >= 0:
        token = tokens[cursor]
        if token.kind == "par":
            return None
        if token.kind in _SKIP_BEFORE_WORD:
            cursor -= 1
            continue
        if token.kind == "word":
            return token.text
        return None
    return None


def _in_tabular_or_array(token: Token) -> bool:
    return any(env_base(env) in {"tabular", "array"} for env in token.envs)


def _tied_before_environment(
    document: Document,
    token: Token,
    positions: dict[int, int],
) -> bool:
    index = positions[id(token)]
    if index == 0 or document.tokens[index - 1].kind != "nbsp":
        return False
    if token.end_offset < 0:
        return False
    source = document.sources.get(token.file, "")
    remainder = source[token.end_offset:]
    line_rest, separator, _ = remainder.partition("\n")
    if separator == "" or strip_comment(line_rest).strip() != "":
        return False
    following = strip_comment(document.line_text(token.file, token.line + 1)).strip()
    return following.startswith("\\begin")


def _breakable_before(tokens: list[Token], index: int) -> bool:
    if index == 0:
        return False
    return tokens[index - 1].kind in {"space", "control_space"}


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


def _diag(
    token: Token,
    message: str,
    rule_id: str,
    severity: str = "error",
) -> Diagnostic:
    return Diagnostic(token.file, token.line, token.col, severity, message, rule_id)
