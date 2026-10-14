from pathlib import Path

from paperlint.engine import lint_path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _lint(tmp_path: Path, text: str, name: str = "main.tex"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return lint_path(path)


def _ids(diagnostics):
    return {item.rule_id for item in diagnostics}


def test_label_prefix_matches_environment(tmp_path: Path):
    bad = _lint(tmp_path, "\\begin{figure}\n\\label{sec:inside}\n\\end{figure}\n")
    assert "label-key" in _ids(bad)
    clean = _lint(tmp_path, "\\begin{figure}\n\\label{fig:inside}\n\\end{figure}\n")
    assert "label-key" not in _ids(clean)


def test_citation_matrix(tmp_path: Path):
    cases = {
        r"see \cite{key}": {"cite-sentence-role"},
        r"see~\cite{key}": {"cite-sentence-role"},
        r"(see \cite{key})": {"cite-sentence-role"},
        r"in~\cite{key}": {"cite-sentence-role"},
        r"Ref.~\cite{key}": {"cite-sentence-role"},
        r"Ref.~\cite{a,b}": {"cite-sentence-role"},
        r"result \cite{key}": {"cite-sentence-role"},
        r"result~\cite{key}": set(),
        r"(see, e.g.,~\cite{key})": set(),
        r"e.g. \cite{key}": {"cite-parenthetical-tie", "abbrev-space"},
        r"e.g.~\cite{key}": set(),
        r"\cite{key}": {"cite-sentence-role"},
        r"\refcite{a,b}": {"cite-plural", "refcite-missing"},
        r"\refscite{only}": {"cite-plural", "refcite-missing"},
        r"\refcite{a} and \refcite{b}": {"cite-plural", "refcite-missing"},
        r"\refcite{key}'s": {"cite-possessive", "refcite-missing"},
        r"\cite[Sec.~2]{key}'s": {"cite-possessive"},
        r"\refcite{a,b}'s": {"cite-possessive", "cite-plural", "refcite-missing"},
        r"see \refcite{key}": {"refcite-missing"},
    }
    for source, expected in cases.items():
        found = _ids(_lint(tmp_path, source + "\n"))
        relevant = found & {
            "cite-sentence-role",
            "cite-parenthetical-tie",
            "cite-plural",
            "cite-possessive",
            "refcite-missing",
            "abbrev-space",
        }
        assert relevant == expected, (source, relevant, expected)
        if "cite-sentence-role" in expected and "cite-parenthetical-tie" in relevant:
            raise AssertionError(source)


def test_sentence_role_message_names_the_trigger(tmp_path: Path):
    diagnostics = _lint(tmp_path, "in~\\cite{key}\n")
    role = next(item for item in diagnostics if item.rule_id == "cite-sentence-role")
    assert 'object of "in"' in role.message
    assert r"\refcite" in role.message

    plural = _lint(tmp_path, "in~\\cite{a,b}\n")
    role = next(item for item in plural if item.rule_id == "cite-sentence-role")
    assert r"\refscite" in role.message


def test_possessive_does_not_recommend_the_possessive_macro(tmp_path: Path):
    diagnostics = _lint(tmp_path, "see \\cite{key}'s\n")
    assert "cite-sentence-role" not in _ids(diagnostics)
    possessive = next(item for item in diagnostics if item.rule_id == "cite-possessive")
    assert "of" in possessive.message
    assert "'s" not in possessive.message.split("of", 1)[1]


def test_bare_cite_is_not_a_missing_key_warning(tmp_path: Path):
    diagnostics = _lint(tmp_path, "\\bibliography{none}\n\\cite{Missing}\n")
    assert "refcite-missing" not in _ids(diagnostics)


def test_lone_qty_is_not_in_math_mode(tmp_path: Path):
    assert "qty-math" in _ids(_lint(tmp_path, r"$\qty{1}{cm}$" + "\n"))
    assert "qty-math" in _ids(_lint(tmp_path, "\\[\\qty{1}{cm}\\]\n"))
    assert "qty-math" in _ids(_lint(
        tmp_path, "\\begin{equation}\n\\qty{1}{cm}\n\\end{equation}\n"
    ))
    assert "qty-math" not in _ids(_lint(tmp_path, r"$a+\qty{1}{cm}$" + "\n"))
    assert "qty-math" not in _ids(_lint(tmp_path, r"The mass is \qty{1}{kg}." + "\n"))


def test_newenvironment_may_contain_begin_and_end(tmp_path: Path):
    source = (
        "\\newenvironment{proof}{\\begin{quote}}{\\end{quote}}\n"
        "\\newcommand{\\wrapped}{\\begin{quote}text\\end{quote}}\n"
        "\\newcommand{\\beq}{\\begin{equation}}\n"
    )
    found = _ids(_lint(tmp_path, source))
    assert "no-env-macro" in found
    assert sum(item.rule_id == "no-env-macro" for item in _lint(tmp_path, source)) == 1


def test_literal_arguments_are_not_style_checked(tmp_path: Path):
    sources = (
        r"\texttt{10 yr and 1-10 and e.g. this}",
        r"\href{https://example.com/10cm}{see 10 yr}",
        r"\url{https://example.com/10^{3}}",
        r"\documentclass[e.g. 10 yr, 1-10]{article}",
        r"\usepackage[margin=1 cm, 10^{3}]{geometry}",
        r"\verb|10 yr|",
        "\\begin{verbatim}\n10 yr\n\\end{verbatim}\n",
    )
    for source in sources:
        found = _ids(_lint(tmp_path, source + "\n"))
        assert "unit-bare" not in found, source
        assert "num-power" not in found, source
        assert "dash-range" not in found, source
        assert "abbrev-space" not in found, source
    assert "unit-bare" in _ids(_lint(tmp_path, r"\texttt{ok} 10 yr" + "\n"))


def test_empty_citation(tmp_path: Path):
    for source in (r"\cite{}", r"\cite{ }", r"\refcite{}", r"\refscite{}", r"result~\cite{}"):
        found = _ids(_lint(tmp_path, source + "\n"))
        assert "cite-empty" in found
        assert "cite-sentence-role" not in found
    assert "cite-empty" not in _ids(_lint(tmp_path, r"\cite{key}" + "\n"))


def test_cite_before_display_stays_parenthetical(tmp_path: Path):
    display = "\\begin{equation}\nx\n\\end{equation}\n"
    assert "cite-sentence-role" not in _ids(_lint(tmp_path, "see~\\cite{key}\n" + display))
    assert "cite-sentence-role" in _ids(_lint(tmp_path, "see \\cite{key}\n" + display))
    assert "cite-sentence-role" in _ids(_lint(tmp_path, "see~\\cite{key} more\n" + display))
    assert "cite-sentence-role" not in _ids(
        _lint(tmp_path, "model~\\cite{key}\n\\begin{figure}\n\\end{figure}\n")
    )


def test_cite_in_tabular_or_array_stays_parenthetical(tmp_path: Path):
    tabular = "\\begin{tabular}{c}\nsee \\cite{key}\n\\end{tabular}\n"
    array = (
        "\\begin{equation}\n\\begin{array}{c}\nsee \\cite{key}\n"
        "\\end{array}\n\\end{equation}\n"
    )
    assert "cite-sentence-role" not in _ids(_lint(tmp_path, tabular))
    assert "cite-sentence-role" not in _ids(_lint(tmp_path, array))
    assert "cite-sentence-role" in _ids(_lint(tmp_path, "see \\cite{key}\n"))


def test_tie_is_required_only_before_cite(tmp_path: Path):
    for source in (
        "in \\cref{fig:a}\n",
        "in\n\\cref{fig:a}\n",
        "in \\refcite{key}\n",
        "in \\refscite{a,b}\n",
    ):
        assert "cite-parenthetical-tie" not in _ids(_lint(tmp_path, source))
    tied = _lint(tmp_path, "e.g. \\cite{key}\n")
    assert "cite-parenthetical-tie" in _ids(tied)


def test_begin_may_end_with_ignorespaces_or_comment(tmp_path: Path):
    clean = (
        "\\begin{abstract}\\ignorespaces\n\\end{abstract}\n"
        "\\begin{abstract}%\n\\end{abstract}\n"
        "\\begin{figure}[ht]\\ignorespaces % placement\n\\end{figure}\n"
    )
    assert "env-own-line" not in _ids(_lint(tmp_path, clean))
    bad = "\\begin{abstract}\\ignorespaces text\n\\end{abstract}\n"
    assert "env-own-line" in _ids(_lint(tmp_path, bad))
    ended = "\\begin{abstract}\n\\end{abstract}\\ignorespaces\n"
    assert "env-own-line" in _ids(_lint(tmp_path, ended))
    short = "\\begin{equation}\n" + ("x" * 80) + "\n\\end{equation}\n"
    long = "\\begin{equation}\n" + ("x" * 81) + "\n\\end{equation}\n"
    assert "display-line-length" not in _ids(_lint(tmp_path, short))
    assert "display-line-length" in _ids(_lint(tmp_path, long))


def test_suppression_and_exit_status(tmp_path: Path):
    path = tmp_path / "main.tex"
    path.write_text("\\ref{sec:a} % paperlint: disable=no-ref\n", encoding="utf-8")
    assert lint_path(path) == []


def test_style_ok_exempts_the_line(tmp_path: Path):
    source = (
        "\\ref{sec:a} %!style ok\n"
        "\\ref{sec:b}\n"
        "e.g. \\ref{sec:c} %!style ok\n"
        "\\ref{sec:d}\\%!style ok\n"
        "\\ref{sec:e} %!style okay\n"
    )
    diagnostics = _lint(tmp_path, source)
    lines = {item.line for item in diagnostics if item.rule_id == "no-ref"}
    assert lines == {2, 4, 5}
    assert "abbrev-space" not in _ids(diagnostics)


def test_warning_only_file_has_no_errors(tmp_path: Path):
    diagnostics = _lint(tmp_path, "e.g. next\n")
    assert diagnostics
    assert all(item.severity == "warning" for item in diagnostics)


def test_unspaced_en_dash_is_not_flagged(tmp_path: Path):
    assert "dash-spacing" not in _ids(_lint(tmp_path, "word--word\n"))
    assert "dash-range" not in _ids(_lint(tmp_path, "See 1--10.\n"))


def test_array_of_words_suggests_tabular(tmp_path: Path):
    source = (
        "\\begin{equation}\n"
        "\\begin{array}{ll}\n"
        "\\text{alpha} & \\text{beta} \\\\\n"
        "\\text{gamma} & \\text{delta} \\\\\n"
        "\\text{epsilon} & \\text{zeta} \\\\\n"
        "\\end{array}\n"
        "\\end{equation}\n"
    )
    assert "table-mathness" in _ids(_lint(tmp_path, source))


def test_powers_of_ten(tmp_path: Path):
    assert "num-scientific" not in _ids(_lint(tmp_path, "$4 \\times 10^{7}$\n"))
    assert "num-power" in _ids(_lint(tmp_path, "$4 \\times 10^{7}$\n"))
    assert "num-scientific" in _ids(_lint(tmp_path, "about 4e7 events\n"))
    assert "num-scientific" not in _ids(_lint(tmp_path, "about \\num{4e7} events\n"))
    assert "num-power" in _ids(_lint(tmp_path, r"2\times10^{-4}" + "\n"))
    assert "num-power" not in _ids(_lint(tmp_path, r"10^{n}" + "\n"))
    assert "num-power" not in _ids(_lint(tmp_path, r"10^{2.5}" + "\n"))
    powered = _lint(tmp_path, "\\documentclass{article}\n$10^{3}$\n")
    message = next(item.message for item in powered if item.rule_id == "num-power")
    assert r"\num{e3}" in message


def test_bare_units(tmp_path: Path):
    assert "unit-bare" in _ids(_lint(tmp_path, r"eV}" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"eV^2" + "\n"))
    assert "unit-bare" not in _ids(_lint(tmp_path, r"eVa" + "\n"))
    assert "unit-bare" not in _ids(_lint(tmp_path, r"kg-yr" + "\n"))
    assert "unit-bare" not in _ids(_lint(tmp_path, r"\qty{10}{eV}" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"M_\odot" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"M_{\odot}x" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"xM_\odot" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"\mu m" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"10 cm" + "\n"))
    assert "unit-bare" not in _ids(_lint(tmp_path, r"$\mathrm{mol}$" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"$\mathrm{cm}$" + "\n"))
    assert "unit-bare" not in _ids(_lint(tmp_path, r"\vspace{1cm}" + "\n"))
    assert "unit-bare" not in _ids(_lint(tmp_path, r"\includegraphics[width=2.5cm]{plot}" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"The gap is 1cm." + "\n"))
    assert "unit-bare" not in _ids(_lint(tmp_path, r"\cite{Smith:2020yr}" + "\n"))
    assert "unit-bare" not in _ids(_lint(tmp_path, r"\refcite{Aalbers:2024pc}" + "\n"))
    assert "cite-plural" in _ids(_lint(tmp_path, r"\refcite{Smith:2020yr,Aalbers:2024pc}" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"\cite[see yr]{Smith:2020}" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"\vspace{1 cm}" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"GeV" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"kpc" + "\n"))
    assert "unit-bare" in _ids(_lint(tmp_path, r"GHz" + "\n"))


def test_preamble_hints(tmp_path: Path):
    missing = _lint(tmp_path, "\\documentclass{article}\nsee \\cite{key}\n")
    hint = next(item for item in missing if item.rule_id == "define-refcite")
    assert hint.line == 1
    assert r"\newcommand{\refcite}[1]{Ref.~\cite{#1}}" in hint.message
    defined = (
        "\\documentclass{article}\n"
        "\\newcommand{\\refcite}[1]{Ref.~\\cite{#1}}\n"
        "see \\cite{key}\n"
    )
    assert "define-refcite" not in _ids(_lint(tmp_path, defined))
    plural = (
        "\\documentclass{article}\n"
        "\\newcommand{\\refcite}[1]{Ref.~\\cite{#1}}\n"
        "\\refcite{a,b}\n"
    )
    assert "define-refscite" in _ids(_lint(tmp_path, plural))
    bars = "\\documentclass{article}\n\\begin{tabular}{l|c}\n\\end{tabular}\n"
    assert "usepackage-booktabs" in _ids(_lint(tmp_path, bars))
    loaded = "\\documentclass{article}\n\\usepackage{booktabs}\n\\begin{tabular}{l|c}\n\\end{tabular}\n"
    assert "usepackage-booktabs" not in _ids(_lint(tmp_path, loaded))
    units = "\\documentclass{article}\n10 cm\n"
    siunitx = _lint(tmp_path, units)
    assert "usepackage-siunitx" in _ids(siunitx)
    assert sum(item.rule_id == "usepackage-siunitx" for item in siunitx) == 1
    assert next(item for item in siunitx if item.rule_id == "usepackage-siunitx").severity == "error"
    with_pkg = "\\documentclass{article}\n\\usepackage[range-units]{siunitx,booktabs}\n10 cm\n"
    assert "usepackage-siunitx" not in _ids(_lint(tmp_path, with_pkg))
    year = "\\documentclass{article}\n\\usepackage{siunitx}\nThe age is 10 yr.\n"
    declared = _lint(tmp_path, year)
    hint = next(item for item in declared if item.rule_id == "declare-si-unit")
    assert hint.line == 3
    assert hint.severity == "error"
    assert r"\DeclareSIUnit{\year}{yr}" in hint.message
    assert "usepackage-siunitx" not in _ids(declared)
    bare_year = "\\documentclass{article}\nThe age is 10 yr.\n"
    assert "usepackage-siunitx" in _ids(_lint(tmp_path, bare_year))
    assert "declare-si-unit" not in _ids(_lint(tmp_path, bare_year))
    ready = (
        "\\documentclass{article}\n"
        "\\usepackage{siunitx}\n"
        "\\DeclareSIUnit{\\year}{yr}\n"
        "\\DeclareSIUnit{\\au}{AU}\n"
        "\\DeclareSIUnit{\\parsec}{pc}\n"
        "The age is 10 yr and the distance is 2 pc and 3 AU.\n"
    )
    assert "declare-si-unit" not in _ids(_lint(tmp_path, ready))
    only_decl = (
        "\\usepackage{siunitx}\n"
        "\\DeclareSIUnit{\\year}{yr}\n"
        "\\DeclareSIUnit{\\au}{AU}\n"
        "\\DeclareSIUnit{\\parsec}{pc}\n"
    )
    assert "unit-bare" not in _ids(_lint(tmp_path, only_decl))


def test_preamble_includes_supply_packages(tmp_path: Path):
    (tmp_path / "setup.tex").write_text(
        "\\usepackage{booktabs}\n"
        "\\usepackage{siunitx}\n"
        "\\DeclareSIUnit{\\year}{yr}\n",
        encoding="utf-8",
    )
    body = (
        "\\begin{document}\n"
        "\\begin{tabular}{l|c}\n\\end{tabular}\n"
        "The age is 10 yr.\n"
    )
    for command in ("\\include{setup}\n", "\\input{setup}\n"):
        source = "\\documentclass{article}\n" + command + body
        found = _ids(_lint(tmp_path, source))
        assert "usepackage-booktabs" not in found, command
        assert "usepackage-siunitx" not in found, command
        assert "declare-si-unit" not in found, command
    late = (
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\input{setup}\n"
        "10 cm\n"
    )
    late_ids = _ids(_lint(tmp_path, late))
    assert "usepackage-siunitx" in late_ids
    assert "declare-si-unit" not in late_ids


def test_demoted_rules_are_warnings(tmp_path: Path):
    source = "\\ref{sec:a}\nsee \\cite{key}\n\\cite{other}'s\n\\begin{figure}[ht]\n\\end{figure}\n"
    diagnostics = _lint(tmp_path, source)
    for rule in ("no-ref", "cite-sentence-role", "cite-possessive", "figure-placement"):
        item = next(entry for entry in diagnostics if entry.rule_id == rule)
        assert item.severity == "warning", rule


def test_bibliography_rules(tmp_path: Path):
    authors = " and ".join(f"Author{i}" for i in range(11))
    bib = f"""
@article{{Known,
  author = {{Ada and Bob}},
  doi = {{10.1/known}},
  eprint = {{1111.2222}},
  url = {{https://example.test/a}}
}}
@article{{Copy,
  author = {{Ada and Bob}},
  doi = {{10.1/known}},
  eprint = {{1111.2222}},
  url = {{https://example.test/a}},
  file = {{:ignored.pdf:PDF}},
  mendeley-groups = {{group}}
}}
@article{{Long,
  author = {{{authors}}},
  title = {{mendeley appears only in the value}}
}}
@article{{Empty,
  doi = {{}},
  eprint = {{}}
}}
@string{{ignored = "nope"}}
@comment{{not an entry}}
"""
    (tmp_path / "refs.bib").write_text(bib, encoding="utf-8")
    diagnostics = _lint(
        tmp_path,
        "\\bibliography{refs}\n\\refcite{Missing}\n\\cite{Missing}\n\\refcite{Known}\n",
    )
    ids = _ids(diagnostics)
    assert "refcite-missing" in ids
    assert "bib-too-many-authors" in ids
    assert "bib-duplicate-doi" in ids
    assert "bib-duplicate-eprint" in ids
    assert "bib-duplicate-url" in ids
    assert "bib-file-field" in ids
    assert "bib-mendeley-field" in ids
    missing = [item for item in diagnostics if item.rule_id == "refcite-missing"]
    assert len(missing) == 1
    assert missing[0].file.suffix == ".tex"
    bib_diags = [item for item in diagnostics if item.rule_id.startswith("bib-")]
    assert bib_diags
    assert all(item.file.suffix == ".bib" for item in bib_diags)
    duplicate = next(item for item in diagnostics if item.rule_id == "bib-duplicate-doi")
    assert "Known" in duplicate.message or "Copy" in duplicate.message


def test_author_others_is_not_counted(tmp_path: Path):
    names = " and ".join(f"Author{i}" for i in range(10))
    (tmp_path / "refs.bib").write_text(
        f"@article{{A, author = {{{names} and others}}}}\n",
        encoding="utf-8",
    )
    diagnostics = _lint(tmp_path, "\\bibliography{refs}\n")
    assert "bib-too-many-authors" not in _ids(diagnostics)


def test_style_ok_exempts_a_bibliography_line(tmp_path: Path):
    (tmp_path / "refs.bib").write_text(
        "@article{A,\n  file = {:ignored.pdf:PDF} %!style ok\n}\n",
        encoding="utf-8",
    )
    diagnostics = _lint(tmp_path, "\\bibliography{refs}\n")
    assert "bib-file-field" not in _ids(diagnostics)


def test_crossref_fields_are_not_inherited(tmp_path: Path):
    (tmp_path / "refs.bib").write_text(
        "@article{Parent, doi = {10.1/parent}}\n"
        "@article{Child, crossref = {Parent}}\n",
        encoding="utf-8",
    )
    diagnostics = _lint(tmp_path, "\\bibliography{refs}\n")
    assert "bib-duplicate-doi" not in _ids(diagnostics)


def test_fixture_pairs():
    rules = sorted(path.name for path in FIXTURES.iterdir() if path.is_dir())
    assert rules
    for rule in rules:
        bad = lint_path(FIXTURES / rule / "bad.tex")
        clean = lint_path(FIXTURES / rule / "clean.tex")
        assert rule in {item.rule_id for item in bad}, rule
        assert rule not in {item.rule_id for item in clean}, rule
