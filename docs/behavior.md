# Linting behavior

This is the behavior of the checker. [`style.tex`](../style.tex) is the style note that motivated it. [`docs/adr/0001-checking-model.md`](adr/0001-checking-model.md) records why the rules were chosen. Where they disagree, this file describes what the program does.

## How a run works

`paperlint` takes one root `.tex` file. It follows `\input` and `\include`, and it does not read `.bbl` or `.aux` files. A file checked on its own starts with an empty environment stack. `subfiles` and the `import` package are not followed.

Each finding is one line:

```text
file:line:col: severity: message [rule-id]
```

Severity is `error` or `warning`. The process exits 1 when any error was reported, and 0 when the only findings are warnings.

The checker does not expand macros and assumes standard catcodes. It ignores comments, `\verb`, `verbatim`, `Verbatim`, `lstlisting`, `minted`, the `comment` environment, and anything after `\end{document}`. `\text`, `\intertext`, `\shortintertext`, `\mbox`, and `\footnote` return to text mode for their argument.

Citation keys, the mandatory argument of `\cite`, `\refcite`, and `\refscite`, are not style-checked. They have to match bibliography entry names. Optional notes such as `\cite[see yr]{key}` are still checked. `cite-empty` and `cite-plural` still look at the keys.

A trailing comment suppresses one rule on that line. Several ids may be separated by commas:

```latex
\ref{sec:old} % paperlint: disable=no-ref
```

`paperlint.toml` next to the root file can replace the label-prefix map, the citation trigger and exclusion lists, the abbreviation list, and the comment-line threshold.

Sentence start is the start of a paragraph, or a position after `.`, `!`, or `?`. Periods that belong to the abbreviation list are not sentence boundaries. Quotes, parentheses, and brackets may sit between the boundary and the following command.

## Errors

### `label-key`

A `\label` has no whitespace, and its argument begins with `sec:`, `eq:`, `fig:`, or `tab:`.

Inside `figure` or `figure*`, the prefix is `fig:`. Inside `table` or `table*`, it is `tab:`. Inside `equation`, `multline`, `align`, or `gather` (and the starred forms), it is `eq:`. Otherwise, after `\section`, `\subsection`, `\subsubsection`, `\paragraph`, or `\subparagraph`, it is `sec:`. A label with no relevant environment and no sectioning command only has to use one of the known prefixes.

### `no-ref`

`\ref` and `\eqref` are forbidden. Use `\cref` or `\Cref`.

### `cref-sentence-case`

`\cref` at the start of a sentence is `\Cref`. `e.g. \cref{fig:a}` does not count as the start of a sentence.

### `cref-combine`

`\cref{eq:a} and \cref{eq:b}` is one `\cref{eq:a,eq:b}`. Both commands must refer only to `eq:` labels.

### `no-display-delims`

`$$...$$` and `\[...\]` are forbidden. Use `equation`. `equation*` is the unnumbered form.

### `no-eqnarray`

`eqnarray` and `eqnarray*` are forbidden.

### `figure-placement`

`figure` and `figure*` take no optional argument. `\begin{figure}[ht]` is an error.

### `booktabs`

A `tabular` or `array` preamble contains no `|`. `\hline`, `\cline`, and `\vline` are forbidden. Horizontal rules are `\toprule`, `\midrule`, and `\bottomrule`.

### `legacy-font`

`\bf`, `\it`, `\rm`, and `\color` are forbidden, including the forms `{\bf ...}`, `{\it ...}`, `{\rm ...}`, and `{\color ...}`. Use `\textbf`, `\textit`, `\mathrm`, and `\textcolor`.

### `mathrm-text`

The argument of `\mathrm` contains a space or a dash. Use `\textnormal`. `\mathrm{mol}` is legal. `\mathrm{cm}` is a unit and is reported by `unit-bare`, not by this rule.

### `env-own-line`

`\begin{...}` and `\end{...}`, including the environment's own arguments, are the only material on their line.

### `no-env-macro`

The replacement text of `\newcommand`, `\renewcommand`, `\newenvironment`, or `\renewenvironment` (starred forms included) contains `\begin` or `\end`. The diagnostic is on the definition.

### `no-tilde-math`

`~` appears in math mode. Use `\,`, `\;`, `\quad`, `\qquad`, or `\hspace`.

### `display-line-length`

A source line strictly inside `equation`, `equation*`, `multline`, or `multline*` is longer than 80 characters. The `\begin` and `\end` lines do not count.

### `cite-empty`

`\cite`, `\refcite`, or `\refscite` has no key. A missing argument, `\cite{}`, and `\cite{ }` all count. Sentence role, the parenthetical tie, and the plural check do not also fire.

### `cite-sentence-role`

`\cite` in text is being used as a word. The repair is `\refcite` for one key and `\refscite` for a comma-separated argument. Parentheses do not matter: `(see \cite{key})` is the same mistake as `see \cite{key}`.

The rule fires when any of these hold:

- `\cite` is at the start of a sentence.
- The nearest word to the left is on the trigger list, whether the gap is a space or `~`.
- A breakable space immediately precedes `\cite`, and the nearest word is not on the exclusion list. A breakable space is a normal space, a newline that wraps a paragraph, or `\ `.

`~` is not a breakable space. `see~\cite{key}` still fires, because `see` is a trigger. The message names the trigger word when there is one. A breakable space at one of these sites does not also ask for `~`.

The nearest word is the closest lexical word to the left. Spaces, `~`, newlines, and punctuation may sit in between. Another word may not. Matching is case-insensitive, and internal periods stay in the word, so `e.g.` stays `e.g.`. In `(see, e.g.,~\cite{key})` the nearest word is `e.g.`, and `see` is not consulted.

These stay parenthetical even when a trigger word precedes `\cite`:

- `\cite` is inside `tabular` or `array`.
- `\cite` follows `~`, ends the line, and the next line begins with `\begin`. A normal space in that position is not this exemption.

`\citet`, `\citep`, and `\onlinecite` are not checked. The rule does not run in math mode.

A normal space before `\cref`, `\Cref`, `\refcite`, or `\refscite` is legal. Those commands already put a word before the number.

Trigger words: `the`, `this`, `that`, `these`, `those`, `a`, `an`, `both`, `either`, `neither`, `another`, `any`, `each`, `every`, `such`, `in`, `of`, `from`, `by`, `with`, `within`, `via`, `per`, `into`, `upon`, `following`, `after`, `before`, `between`, `among`, `against`, `unlike`, `like`, `despite`, `beyond`, `across`, `under`, `over`, `about`, `through`, `during`, `including`, `except`, `versus`, `vs`, `vs.`, `to`, `on`, `for`, `as`, `see`, `compare`, `consult`, `follow`, `follows`, `followed`, `following`, `use`, `uses`, `used`, `using`, `adopt`, `adopts`, `adopted`, `also`, `Ref.`, `Refs.`, and `cf.`.

`Ref.~\cite{key}` and `Refs.~\cite{a,b}` are this same error. The key count chooses `\refcite` or `\refscite`.

Exclusion words: `e.g.`, `i.e.`, `etc.`, and `al.`. These keep a parenthetical `\cite`. `et al.~\cite{key}` stays a citation of the authors. `cf.` is a trigger, not an exclusion.

`word~\cite{key}` is legal when `word` is neither a trigger nor an exclusion. A verb after the citation is not a signal: `model~\cite{key} shows` is parenthetical.

### `cite-plural`

- `\refcite` with a comma-separated argument should be `\refscite`.
- `\refscite` with a single key should be `\refcite`.
- `\refcite{a} and \refcite{b}` should be `\refscite{a,b}`.

### `cite-possessive`

`'s` immediately after `\cite`, `\refcite`, or `\refscite` is a possessive, including `\cite[Sec.~2]{key}'s`. The repair is a rephrase, typically `of \refcite{key}` or `of \refscite{a,b}`. The checker does not suggest `\refcite{key}'s`.

When the possessive is present, `cite-sentence-role` does not also fire. A plural mismatch on the same command still fires, and the rephrase uses the plural macro.

## Warnings

### `cite-parenthetical-tie`

The nearest word is on the exclusion list and a breakable space immediately precedes `\cite`. Use `~`, as in `e.g.~\cite{key}`. This does not fire together with `cite-sentence-role`.

### `align-single`

An `align` or `align*` contains one line break and one relation (`=`, `\equiv`, `\approx`, `\propto`, or `\simeq`). Use `multline`.

### `array-piecewise`

An `array` that is not inside a `table` has a last column containing `\ll`, `\gg`, `\text`, or a word. Use `cases`.

### `table-mathness`

For an environment with at least six content tokens, a `tabular` whose tokens are more than three quarters math should be an `array`, and an `array` whose tokens are more than half words should be a `tabular`. Spaces, punctuation, math-shift delimiters, `\\`, and text-producing commands such as `\text` are not content tokens.

### `dash-range`

In text, a number, a single hyphen, and a number, as in `1-10`, should be an en dash `1--10`.

### `dash-spacing`

In text, a space or `\ ` immediately before or after `--` or `---` is forbidden. An unspaced en dash used as punctuation, `word--word`, is not flagged.

### `unary-sim`

In math, `\sim` has no left operand. Use `{\sim}` or `\mathop{\sim}`. A group that contains only `\sim`, and `\mathop{\sim}`, are already in the legal form.

### `comment-block`

More than four consecutive lines whose first non-whitespace character is `%`. The threshold is `comment_line_threshold` in `paperlint.toml`. Use the `comment` environment.

### `display-blank-line`

A blank line immediately precedes `\begin` or follows `\end` of `equation`, `multline`, `align`, or `gather`, including starred forms. Blank lines around `figure` and `table` are legal.

### `abbrev-space`

An abbreviation followed by a normal space or a wrapping newline needs `\ ` or `\@.`. `~` and `\ ` do not fire. The default abbreviations are `e.g.`, `i.e.`, `etc.`, `cf.`, `Fig.`, `Eq.`, `eq.`, `vs.`, `al.`, `Ref.`, and `Refs.`.

### `num-scientific`

In text, outside `\num`, a number written `4e7` or `4E-3` should use `\num`. This does not apply in math mode.

### `unit-bare`

A bare unit outside `\qty` should use `\qty`. The scan skips comments, `\verb`, verbatim-like environments, both arguments of `\qty` (and an optional `[...]`), both arguments of `\DeclareSIUnit`, and the key argument of `\cite`, `\refcite`, and `\refscite`. Optional citation notes are still scanned. The same skip applies to `num-power`.

The unit list is `nm`, `\mu m` (a space or `\,` may sit between `\mu` and `m`), `mm`, `cm`, `km`, `pc`, `AU`, `eV`, `kg`, `yr`, and `Hz`. Matching is case-sensitive.

The character after the unit must not be a letter or a hyphen, and the character before it must not be a hyphen. `eVa` and `kg-yr` are legal. `eV}`, `eV^2`, and `eV2` are not. A letter before the unit still matches, so `GeV` is `eV`, `kpc` is `pc`, and `GHz` is `Hz`.

`cm` is exempt when a number immediately precedes it inside a macro argument, as in `\vspace{1cm}` or `\includegraphics[width=2.5cm]{plot}`. `1cm` in prose, and `1 cm` with a space, still warn.

`M_\odot` and `M_{\odot}` warn even when a letter follows or precedes them.

`\mathrm{mol}` does not warn. `\mathrm{cm}` does, because `cm` is on the list.

### `num-power`

`10^x` or `10^{x}`, in text or in math, where `x` is an optional sign and digits. `10^{n}` and `10^{2.5}` do not match. A mantissa written with `\times` or `×` immediately before the power is part of the match.

| Source | Suggestion |
| --- | --- |
| `10^{3}` | `\num{e3}` |
| `10^{-3}` | `\num{e-3}` |
| `2\times10^{3}` | `\num{2e3}` |
| `2 \times 10^{-4}` | `\num{2e-4}` |

The arguments of `\num` and `\qty`, and citation keys, are skipped.

### `qty-math`

`$...$`, `\(...\)`, `$$...$$`, `\[...\]`, or an `equation`, `multline`, `align`, or `gather` environment (starred forms included) contains nothing but one `\qty` and whitespace. `\qty` inside a larger formula stays legal, and `\qty` in text stays legal.

### `refcite-missing`

A key passed to `\refcite` or `\refscite` is absent from the `.bib` files named by `\bibliography` or `\addbibresource`. One warning per missing key, on the command. A missing key of `\cite` is left to the compiler. An empty citation is `cite-empty`, not this rule.

### `bib-too-many-authors`

The `author` field has more than 10 names. Names are split on `and` at brace depth zero. `others` does not count. The message suggests `` `and others` `` instead of listing every name.

### `bib-duplicate-eprint`, `bib-duplicate-doi`, `bib-duplicate-url`

The field value matches another entry in the same bibliography set. Values are compared after trimming whitespace, removing outer braces, and collapsing internal whitespace. Empty values do not match. Each entry in a matching set is warned, and the message names the other keys. `10.1000/abc` and `https://doi.org/10.1000/abc` are not the same value.

### `bib-file-field`

The entry has a field named `file`.

### `bib-mendeley-field`

The entry has a field whose name contains `mendeley`, such as `mendeley-groups` or `mendeley-tags`. A value that merely contains the word does not match.

Every entry in the named `.bib` files is checked, cited or not. `@string`, `@preamble`, and `@comment` are not entries. Field names are matched case-insensitively. Only fields written on the entry count; `crossref` is not inherited. Diagnostics point at the `.bib` file.

## Preamble hints

These are warnings. `define-refcite`, `define-refscite`, `usepackage-booktabs`, and `usepackage-siunitx` sit on the `\documentclass` line, column 1. If the file has no `\documentclass`, they sit on line 1 of the root file.

### `define-refcite` and `define-refscite`

`cite-sentence-role`, `cite-plural`, or `cite-possessive` tells the author to use that command, and the source never defines it. A definition is `\newcommand`, `\renewcommand`, `\providecommand`, or `\DeclareRobustCommand`, with an optional star, or `\def`. The message includes:

```latex
\newcommand{\refcite}[1]{Ref.~\cite{#1}}
\newcommand{\refscite}[1]{Refs.~\cite{#1}}
```

### `usepackage-booktabs`

`booktabs` fired, and neither `\usepackage` nor `\RequirePackage` loads `booktabs`. The message asks for `\usepackage{booktabs}`.

### `usepackage-siunitx`

`unit-bare`, `num-power`, or `num-scientific` fired, and `siunitx` is not loaded. One warning even if several of those rules fired. The message asks for `\usepackage{siunitx}`.

Options and combined lists count: `\usepackage[range-units]{siunitx,booktabs}`.

### `declare-si-unit`

`yr`, `pc`, and `AU` are not built into siunitx. When one of those `unit-bare` findings is present and `siunitx` is loaded, this warning sits on the line after the `\usepackage` or `\RequirePackage` that loads it. The message asks for the missing declaration:

```latex
\DeclareSIUnit{\year}{yr}
\DeclareSIUnit{\parsec}{pc}
\DeclareSIUnit{\au}{AU}
```

A `\DeclareSIUnit` that already names `\year`, `\parsec`, or `\au` suppresses that hint. When `siunitx` itself is missing, `usepackage-siunitx` is the hint instead.

## Not checked

- Undefined labels, and missing keys of a bare `\cite`.
- An unspaced en dash used as punctuation (`word--word`).
- A semicolon that precedes a space but does not end a clause.
- Whether a table is largely mathematical, beyond the `table-mathness` threshold.
- Whether a blank line was meant as a paragraph break, beyond `display-blank-line`.
- Whether a long equation is organized, beyond the 80-column limit.
- A following verb as proof that `\cite` is the subject (`model~\cite{key} shows`).
- Single-letter units such as `m`, `s`, `g`, and `K`.
