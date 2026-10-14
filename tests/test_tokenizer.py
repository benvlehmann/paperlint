from pathlib import Path

from paperlint.config import Config, load_config
from paperlint.tokenize import load_document

ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "style.tex"


def _parse(tmp_path: Path, text: str, name: str = "main.tex"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return load_document(path, Config())


def _commands(document, name: str):
    return [token for token in document.tokens if token.kind == "command" and token.name == name]


def test_style_tex_hides_verb_commands():
    document = load_document(STYLE, Config())
    names = {token.name for token in document.tokens if token.kind == "command"}
    assert "ref" not in names
    assert "eqref" not in names


def test_inline_and_display_delimiters(tmp_path: Path):
    document = _parse(tmp_path, r"a $b$ c \(d\) e $$f$$ g \[h\]")
    kinds = [(token.kind, token.text, token.mode) for token in document.tokens if token.kind in {
        "math_shift", "display_open", "display_close", "word", "number",
    }]
    words = [token for token in document.tokens if token.kind == "word"]
    modes = {token.text: token.mode for token in words}
    assert modes["a"] == "text"
    assert modes["b"] == "inline"
    assert modes["c"] == "text"
    assert modes["d"] == "inline"
    assert modes["e"] == "text"
    assert modes["f"] == "display"
    assert modes["g"] == "text"
    assert modes["h"] == "display"
    assert any(token.kind == "display_open" and token.text == "$$" for token in document.tokens)
    assert any(token.kind == "display_open" and token.text == r"\[" for token in document.tokens)
    assert kinds


def test_text_inside_math(tmp_path: Path):
    document = _parse(tmp_path, r"\begin{equation}\text{see \cite{key}}\end{equation}")
    cite = _commands(document, "cite")
    assert len(cite) == 1
    assert cite[0].mode == "text"
    assert "equation" in cite[0].envs


def test_intertext_returns_to_text(tmp_path: Path):
    document = _parse(
        tmp_path,
        "\\begin{align}\n a \n\\intertext{between}\n b \n\\end{align}\n",
    )
    between = next(token for token in document.tokens if token.kind == "word" and token.text == "between")
    assert between.mode == "text"


def test_linebreak_optional_argument_is_not_display_math(tmp_path: Path):
    document = _parse(tmp_path, "\\begin{multline}\n a \\\\[3mm]\n b \n\\end{multline}\n")
    assert not any(token.kind == "display_open" for token in document.tokens)
    assert any(token.name == "\\\\" for token in document.tokens if token.kind == "command")


def test_input_keeps_environment_stack(tmp_path: Path):
    (tmp_path / "chap.tex").write_text("x\n", encoding="utf-8")
    document = _parse(tmp_path, "\\begin{equation}\n\\input{chap}\n\\end{equation}\n")
    word = next(token for token in document.tokens if token.kind == "word" and token.text == "x")
    assert "equation" in word.envs

    alone = load_document(tmp_path / "chap.tex", Config())
    alone_word = next(token for token in alone.tokens if token.text == "x")
    assert alone_word.envs == ()


def test_abbreviation_period_is_not_a_sentence_boundary(tmp_path: Path):
    document = _parse(tmp_path, r"e.g. \cref{fig:a}")
    cref = _commands(document, "cref")[0]
    assert cref.at_sentence_start is False
    period = next(token for token in document.tokens if token.kind == "word" and token.text.casefold() == "e.g.")
    assert period.text == "e.g."


def test_real_period_starts_a_sentence(tmp_path: Path):
    document = _parse(tmp_path, r"Done. \cref{fig:a}")
    cref = _commands(document, "cref")[0]
    assert cref.at_sentence_start is True


def test_skipped_environments_and_end_document(tmp_path: Path):
    document = _parse(
        tmp_path,
        "\\begin{verbatim}\n\\ref{sec:a}\n\\end{verbatim}\n"
        "after\n"
        "\\end{document}\n"
        "\\ref{sec:b}\n",
    )
    assert _commands(document, "ref") == []
    assert any(token.text == "after" for token in document.tokens)


def test_suppression_comment_is_recorded(tmp_path: Path):
    document = _parse(tmp_path, "\\ref{sec:a} % paperlint: disable=no-ref\n")
    assert document.suppressions
    assert "no-ref" in next(iter(document.suppressions.values()))


def test_config_override(tmp_path: Path):
    (tmp_path / "paperlint.toml").write_text(
        'comment_line_threshold = 1\ntriggers = ["only"]\n',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.comment_line_threshold == 1
    assert config.triggers == frozenset({"only"})
    assert "e.g." in config.exclusions


def test_aux_and_bbl_are_not_opened(tmp_path: Path):
    (tmp_path / "main.bbl").write_text("\\ref{sec:nope}\n", encoding="utf-8")
    document = _parse(tmp_path, "\\input{main.bbl}\n\\input{main.aux}\nseen\n")
    assert _commands(document, "ref") == []
    assert any(token.text == "seen" for token in document.tokens)
