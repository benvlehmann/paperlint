from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_TRIGGERS = (
    "the", "this", "that", "these", "those", "a", "an", "both", "either",
    "neither", "another", "any", "each", "every", "such",
    "in", "of", "from", "by", "with", "within", "via", "per", "into", "upon",
    "following", "after", "before", "between", "among", "against", "unlike",
    "like", "despite", "beyond", "across", "under", "over", "about", "through",
    "during", "including", "except", "versus", "vs", "vs.", "to", "on", "for",
    "as",
    "see", "compare", "consult", "follow", "follows", "followed", "following",
    "use", "uses", "used", "using", "adopt", "adopts", "adopted", "also",
    "Ref.", "Refs.", "cf.",
)

DEFAULT_EXCLUSIONS = ("e.g.", "i.e.", "etc.", "al.")

DEFAULT_ABBREVIATIONS = (
    "e.g.", "i.e.", "etc.", "cf.", "Fig.", "Eq.", "eq.", "vs.", "al.",
    "Ref.", "Refs.",
)

DEFAULT_LABEL_ENVS = {
    "sec:": [
        "section", "subsection", "subsubsection", "paragraph", "subparagraph",
    ],
    "eq:": ["equation", "multline", "align", "gather"],
    "fig:": ["figure"],
    "tab:": ["table"],
}

def _folded(items: tuple[str, ...] | list[str]) -> frozenset[str]:
    return frozenset(item.casefold() for item in items)


@dataclass
class Config:
    comment_line_threshold: int = 4
    triggers: frozenset[str] = field(default_factory=lambda: _folded(DEFAULT_TRIGGERS))
    exclusions: frozenset[str] = field(
        default_factory=lambda: _folded(DEFAULT_EXCLUSIONS)
    )
    abbreviations: frozenset[str] = field(
        default_factory=lambda: _folded(DEFAULT_ABBREVIATIONS)
    )
    label_envs: dict[str, list[str]] = field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_LABEL_ENVS.items()}
    )

    @property
    def label_prefixes(self) -> tuple[str, ...]:
        return tuple(self.label_envs)


def load_config(directory: Path) -> Config:
    path = directory / "paperlint.toml"
    config = Config()
    if not path.is_file():
        return config
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if "comment_line_threshold" in data:
        config.comment_line_threshold = int(data["comment_line_threshold"])
    if "triggers" in data:
        config.triggers = _folded(tuple(data["triggers"]))
    if "exclusions" in data:
        config.exclusions = _folded(tuple(data["exclusions"]))
    if "abbreviations" in data:
        config.abbreviations = _folded(tuple(data["abbreviations"]))
    if "label_prefixes" in data:
        config.label_envs = {
            str(prefix): [str(name) for name in names]
            for prefix, names in data["label_prefixes"].items()
        }
    return config
