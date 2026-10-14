# ADR 0001: Checking model for paperlint

- Status: Accepted
- Date: 2026-10-13

## Context

`style.tex` records convention preferences for papers written in LaTeX. paperlint checks as many of those conventions as can be decided from the source without guessing what the author meant.

LaTeX is a poor fit for a whole-file regular expression. Spacing, dashes, units, `\sim`, and citations change meaning between text and math, and between a parenthetical citation and a citation used as a word. The checker therefore starts from a mode-and-environment model, and each rule is either reliable enough to fail a run or heuristic enough that a false positive must be suppressible.

`style.tex` itself is not a clean fixture. Counterexamples appear inside `\verb`, and the affiliation line is a documented dash exception.

## Decision

paperlint is a Python command-line checker with a small tokenizer. It reports diagnostics as

```text
file:line:col: severity: message [rule-id]
```

Rule ids are stable. Severity is `error` or `warning`. JSON output can wait.

### Invocation

paperlint takes one root `.tex` file. It follows `\input` and `\include` from that file and checks included files in the inclusion context. It does not read `.bbl` or `.aux` files. A file checked on its own starts with an empty environment stack. `subfiles`, the `import` package, and linting a chapter whose preamble lives in another file are outside this model.

The process exits 1 when any error was reported. Warnings alone exit 0.

### What the tokenizer provides

The tokenizer tracks:

- text, inline math, and display math, including `$...$`, `\(...\)`, `$$`, `\[...\]`, and math environments (`equation`, `equation*`, `multline`, `align`, `gather`, `cases`, and starred forms)
- the environment stack
- brace groups, well enough to read the argument of `\mathrm`, `\label`, `\cref`, `\cite`, `\refcite`, and `\refscite`

`\text`, `\intertext`, `\shortintertext`, `\mbox`, and `\footnote` are temporary returns to text mode. The tokenizer ignores comments, `\verb`, `verbatim`, `Verbatim`, `lstlisting`, `minted`, the `comment` environment, and anything after `\end{document}`. It follows `\input` and `\include`. It assumes standard catcodes and does not expand macros. A macro that hides `\begin` is reported at its definition rather than reconstructed at the call site.

### Sentence boundaries

Sentence start is the start of a paragraph, or a position after `.`, `!`, or `?`. Periods that belong to the abbreviation list are not sentence boundaries: `e.g. \cref{fig:a}` does not ask for `\Cref`, and `e.g. \cite{key}` is not a sentence-initial citation. Quotes, parentheses, and brackets may intervene and do not cancel sentence start.

### Rule tiers

**Errors** are decided from tokens and the environment stack. **Warnings** are heuristics with an expected false-positive rate; each one is suppressible. A few style-guide statements stay prose: whether a table is “largely mathematical,” whether a blank line was meant as a paragraph break, and whether long equations are “organized,” beyond the 80-column limit below.

Build the math-mode tracker and the error rules first, including the citation errors. Add the warning rules for `align`-versus-`multline`, units, and dashes only after that tracker is tested.

### Errors

| Rule id | Check |
| --- | --- |
| `label-key` | A `\label` argument has no spaces and begins with a configured prefix. Default prefixes: `sec:`, `eq:`, `fig:`, `tab:`. The prefix matches the enclosing environment: `sec:` in sectioning commands, `eq:` in `equation`, `multline`, `align`, and `gather` (starred forms included), `fig:` in `figure` and `figure*`, `tab:` in `table` and `table*`. |
| `no-ref` | `\ref` and `\eqref` are forbidden. Cross-references use `\cref` and `\Cref`. |
| `cref-sentence-case` | `\cref` at the start of a sentence is `\Cref`. Sentence start is defined above. |
| `cref-combine` | Adjacent equation references joined by `and`, as in `\cref{eq:a} and \cref{eq:b}`, are one `\cref{eq:a,eq:b}`. |
| `no-display-delims` | `$$` and `\[...\]` are forbidden. Display math uses the `equation` environment. `equation*` is the unnumbered form. |
| `no-eqnarray` | `eqnarray` is forbidden. |
| `figure-placement` | `figure` and `figure*` take no optional argument. |
| `booktabs` | A tabular or array preamble contains no vertical rule. `\vline`, `\hline`, and `\cline` are forbidden. Horizontal rules are `\toprule`, `\midrule`, and `\bottomrule`. |
| `legacy-font` | `{\bf ...}`, `{\it ...}`, `{\rm ...}`, `{\color ...}`, and the declarations `\bf`, `\it`, and `\rm`, are forbidden. Replacements are `\textbf`, `\textit`, `\mathrm`, and `\textcolor`. |
| `mathrm-text` | The argument of `\mathrm` contains a space or a dash. Use `\textnormal`. |
| `env-own-line` | `\begin{...}` and `\end{...}` each occupy their own line. |
| `no-env-macro` | The replacement text of `\newcommand`, `\renewcommand`, `\newenvironment`, or `\renewenvironment` contains `\begin` or `\end`. The diagnostic is on the definition. |
| `no-tilde-math` | `~` appears in math mode. |
| `display-line-length` | A source line inside `equation`, `equation*`, `multline`, or `multline*` exceeds 80 characters. |
| `cite-sentence-role` | `\cite` is used as a word in the sentence. See below. |
| `cite-plural` | The singular and plural citation macros disagree with the number of keys. See below. |
| `cite-possessive` | A possessive is attached to a citation command. See below. |
| `cite-empty` | `\cite`, `\refcite`, or `\refscite` has no citation key. |

`array` stays legal. Tables of mathematics use it.

### Warnings

| Rule id | Check |
| --- | --- |
| `align-single` | An `align` contains a single line break and a single relation. Suggest `multline`. |
| `array-piecewise` | An `array` has a last column that looks like conditions (`\ll`, `\gg`, `\text`, or words). Suggest `cases`. |
| `num-scientific` | A bare scientific number such as `4e7` appears outside `\num`, in text. |
| `unit-bare` | A bare unit (`cm`, `eV`, `M_\odot`, and the list below) appears outside `\qty`. |
| `num-power` | An integer power `10^x` or `10^{x}` appears outside `\num`. Suggest `\num{yex}`. |
| `define-refcite` | A finding tells the author to use `\refcite`, and that command is not defined. |
| `define-refscite` | A finding tells the author to use `\refscite`, and that command is not defined. |
| `usepackage-booktabs` | Rule `booktabs` fired and `booktabs` is not loaded. |
| `usepackage-siunitx` | A siunitx finding fired and `siunitx` is not loaded. |
| `table-mathness` | A `tabular` is almost entirely math, or an `array` is almost entirely words. |
| `dash-range` | A number–hyphen–number in text, such as `1-10`, should be an en dash. |
| `dash-spacing` | A space surrounds `--` or `---`. |
| `unary-sim` | `\sim` has no left operand. Suggest `{\sim}` or `\mathop{\sim}`. |
| `comment-block` | More than a configured number of consecutive `%` lines appear. Default threshold: 4. Suggest the `comment` environment. |
| `display-blank-line` | A blank line immediately precedes or follows a display-math environment. Blank lines around `figure` and `table` stay legal. |
| `abbrev-space` | An abbreviation on a configured list (`e.g.`, `i.e.`, `cf.`, `Fig.`, and similar) is followed by a breakable space. Require `\ ` or `\@.`. |
| `qty-math` | A math group or display environment contains only `\qty`. Move it out of math mode. |
| `cite-parenthetical-tie` | A parenthetical `\cite` kept by the exclusion list below is preceded by a breakable space. Suggest `~`. |
| `refcite-missing` | A key passed to `\refcite` or `\refscite` is absent from the document’s `.bib` files. See below. |
| `bib-too-many-authors` | An entry’s `author` field lists more than 10 names. See below. |
| `bib-duplicate-eprint` | Two entries have the same `eprint` value. See below. |
| `bib-duplicate-doi` | Two entries have the same `doi` value. See below. |
| `bib-duplicate-url` | Two entries have the same `url` value. See below. |
| `bib-file-field` | An entry has a field named `file`. |
| `bib-mendeley-field` | An entry has a field whose name contains `mendeley`. |

### Citations

Parentheses do not decide citation role. `(see \cite{key})` is the same mistake as `see \cite{key}`. The repair is `\refcite` or `\refscite`, which expand to `Ref.~\cite` and `Refs.~\cite`.

The sentence-role rule applies to `\cite` in text mode only. `\citet`, `\citep`, and `\onlinecite` are outside it. Word-class checks do not run in math mode.

#### Nearest word

Take the nearest lexical word to the left of `\cite`. Spaces, `~`, newlines, and punctuation may sit in between. Another word may not. Match case-insensitively. Internal periods stay part of the word, so `e.g.` remains `e.g.`.

Do not look past that nearest word. In `(see, e.g.,~\cite{key})` the nearest word is `e.g.`, and `see` is not consulted.

#### When `\cite` is a sentence role

Emit `cite-sentence-role` once for a site when any of these hold:

- `\cite` is at the start of a sentence, as defined under Sentence boundaries.
- The nearest word is on the trigger list, whether the gap is a breakable space or `~`.
- A breakable space immediately precedes `\cite` and the nearest word is not on the exclusion list. Breakable space means a normal space, a newline in text mode, or `\ `.

`~` is not breakable space. `see~\cite{key}` is still a sentence role, because `see` is a trigger.

The message names the trigger word when there is one: the citation is the object of “in”; use `\refcite`. Choose the macro from the keys:

- one key: `\refcite`
- a comma-separated argument: `\refscite`

A breakable space at one of these sites does not also produce a “use `~`” diagnostic. `see~\cite{key}` is the same sentence role with a tie added.

Two sites stay parenthetical even when a trigger word precedes the citation. `\cite` inside `tabular` or `array` is one. The other is a `\cite` that follows `~`, ends its line, and whose next line begins with `\begin`: the citation is hanging in front of a display, not acting as a word in the sentence. A breakable space in that position is not this exemption.

#### Trigger list

Configurable. Defaults:

- Determiners: `the`, `this`, `that`, `these`, `those`, `a`, `an`, `both`, `either`, `neither`, `another`, `any`, `each`, `every`, `such`
- Prepositions: `in`, `of`, `from`, `by`, `with`, `within`, `via`, `per`, `into`, `upon`, `following`, `after`, `before`, `between`, `among`, `against`, `unlike`, `like`, `despite`, `beyond`, `across`, `under`, `over`, `about`, `through`, `during`, `including`, `except`, `versus`, `vs`, `vs.`, `to`, `on`, `for`, `as`
- Verbs and `see also`: `see`, `compare`, `consult`, `follow`, `follows`, `followed`, `following`, `use`, `uses`, `used`, `using`, `adopt`, `adopts`, `adopted`, `also`
- Hand-rolled reference words: `Ref.`, `Refs.`
- `cf.`

`Ref.~\cite{key}` and `Refs.~\cite{key}` use this same diagnostic. There is no separate hand-rolled-form rule and no exclusion for those words. Key count still picks `\refcite` or `\refscite`, so `Ref.~\cite{a,b}` asks for `\refscite`.

#### Exclusion list

Configurable. Defaults: `e.g.`, `i.e.`, `etc.`, `al.`.

These keep a parenthetical `\cite`. `et al.~\cite{key}` stays a citation of the authors. A breakable space before `\cite` in this case is `cite-parenthetical-tie`: suggest `~`, and do not emit `cite-sentence-role`.

`cf.` is a trigger, on the same footing as `compare`. Moving it onto the exclusion list is a configuration change.

#### Plural

`cite-plural` fires when:

- `\refcite` has a comma-separated argument. Use `\refscite`.
- `\refscite` has a single key. Use `\refcite`.
- `\refcite{a} and \refcite{b}` should be `\refscite{a,b}`.

#### Possessive

Optional arguments are part of `\cite`, `\refcite`, and `\refscite`. `cite-possessive` fires when `'s` is immediately after the whole call, so `\cite[Sec.~2]{key}'s` matches. Plural checks and `refcite-missing` read keys from the mandatory argument.

This diagnostic is separate from sentence role. `\refcite{key}'s` expands to “Ref. [1]'s”, so the checker must not recommend that spelling. The repair is a rephrase, typically “of `\refcite{key}`” or “of `\refscite{a,b}`”.

When the possessive is present, skip `cite-sentence-role` for that command. A plural mismatch on the same command still reports `cite-plural`, and the possessive message uses the plural macro in the rephrase.

#### Citations the checker leaves alone

`word~\cite{key}` is legal when `word` is neither a trigger nor an exclusion. A following verb is not a signal: `model~\cite{key} shows` places a parenthetical citation between a noun and its verb. A conjunction-plus-verb pattern (`and \cite{key} shows`) waits until `cite-sentence-role` has been run on a real paper.

A tie is required only before `\cite`. A bare citation number should not start a line, and `\cite` produces only that number. `\cref`, `\Cref`, `\refcite`, and `\refscite` already place descriptive text before the number (“figure”, “Ref.”, “Refs.”), and the tie they need sits inside that text. A normal space before those commands is legal.

#### Empty citations

`cite-empty` fires when `\cite`, `\refcite`, or `\refscite` has no key. That includes a missing argument and an empty group such as `\cite{}` or `\cite{ }`. Sentence role, the parenthetical tie, and the plural check do not also fire.

#### Preamble hints

These warnings sit on the `\documentclass` line. If the file has no `\documentclass`, they sit on line 1 of the root file.

`define-refcite` and `define-refscite` fire when `cite-sentence-role`, `cite-plural`, or `cite-possessive` tells the author to use that command and the source never defines it. A definition is `\newcommand`, `\renewcommand`, `\providecommand`, or `\DeclareRobustCommand`, with an optional star, or `\def`. The message includes the corresponding line:

```latex
\newcommand{\refcite}[1]{Ref.~\cite{#1}}
\newcommand{\refscite}[1]{Refs.~\cite{#1}}
```

`usepackage-booktabs` fires when `booktabs` fired and neither `\usepackage` nor `\RequirePackage` loads `booktabs`. `usepackage-siunitx` fires once when `unit-bare`, `num-power`, or `num-scientific` fired and `siunitx` is not loaded. Options and combined package lists count.

`yr`, `pc`, and `AU` are not built into siunitx. When one of those `unit-bare` findings is present and `siunitx` is loaded, `declare-si-unit` fires on the line after the `\usepackage` or `\RequirePackage` that loads it. The message asks for the missing declaration:

```latex
\DeclareSIUnit{\year}{yr}
\DeclareSIUnit{\parsec}{pc}
\DeclareSIUnit{\au}{AU}
```

A declaration already in the source suppresses that hint. When `siunitx` itself is missing, `usepackage-siunitx` is the hint instead.

#### Bare units and powers of ten

`unit-bare` scans the source, skipping comments, `\verb`, verbatim-like environments, both arguments of `\qty` (including an optional bracket argument), both arguments of `\DeclareSIUnit`, and the citation-key argument of `\cite`, `\refcite`, and `\refscite`. Optional citation notes stay visible. The key text has to match a bibliography entry name, so it is not a style violation. `cite-plural` still compares the number of keys. A unit matches only when the character after it is not a letter or a hyphen, and the character before it is not a hyphen. `eVa` and `kg-yr` are legal. `eV}`, `eV^2`, and `eV2` are not. A letter before the unit still matches, so `GeV` is caught as `eV`, `kpc` as `pc`, and `GHz` as `Hz`. `cm` is exempt when a number immediately precedes it inside a macro argument, as in `\vspace{1cm}`: that is a TeX length. `1cm` in prose, and `1 cm` with a space, still warn. The default list is `nm`, `\mu m` (optional space or `\,`), `mm`, `cm`, `km`, `pc`, `AU`, `eV`, `kg`, `yr`, and `Hz`. `M_\odot` and `M_{\odot}` match even when a letter follows. Single-letter units are not on the list.

`num-power` matches `10^x` and `10^{x}` when `x` is an optional sign and digits, in text or in math. `10^{n}` and `10^{2.5}` do not match. A mantissa written with `\times` or `×` immediately before the power is part of the match: `2\times10^{3}` asks for `\num{2e3}`, `2 \times 10^{-4}` asks for `\num{2e-4}`, and `10^{3}` asks for `\num{e3}`. The argument of `\num`, and both arguments of `\qty`, are skipped. `num-scientific` remains the check for a bare `4e7` in text outside `\num`.

`qty-math` fires when `$\qty{x}{y}$`, `\(\qty{x}{y}\)`, `$$\qty{x}{y}$$`, `\[\qty{x}{y}\]`, or an `equation`, `multline`, `align`, or `gather` environment contains nothing but one `\qty` and whitespace. `\qty` inside a larger formula stays legal.

#### Missing keys

`refcite-missing` warns when a key passed to `\refcite` or `\refscite` is absent from the `.bib` files named by `\bibliography` or `\addbibresource`. Keys are split on commas. One diagnostic is reported per missing key, on the command. A missing key of `\cite` stays the compiler’s job.

### Bibliography

Every entry in those `.bib` files is checked, whether or not it is cited. `@string`, `@preamble`, and `@comment` are not entries. Field names are matched case-insensitively. Only fields written on the entry itself count; values inherited through `crossref` are ignored. Diagnostics point at the `.bib` file. An entry with several problems produces one warning per problem.

`bib-too-many-authors` fires when the `author` field has more than 10 names. Names are split on `and` at brace depth zero. `others` does not count as a name. The message suggests writing `and others` instead of listing every name.

`bib-duplicate-eprint`, `bib-duplicate-doi`, and `bib-duplicate-url` fire when the corresponding field value matches another entry in the same bibliography set. Values are compared after trimming whitespace, removing outer braces, and collapsing internal whitespace. Empty values do not match. Each entry in a matching set is warned, and the message names the other keys.

`bib-file-field` fires when a field named `file` is present. `bib-mendeley-field` fires when a field name contains `mendeley`, which covers `mendeley-groups` and `mendeley-tags`. A value that merely contains the word “mendeley” does not match.

### Suppression and configuration

A trailing comment suppresses one rule on that line:

```latex
% paperlint: disable=dash-spacing
```

Configuration supplies the label-prefix map, the citation trigger and exclusion lists, the abbreviation list, the unit lexicon, and the comment-line threshold.

### Outside this model

- Undefined labels. The compiler reports them.
- An en dash used as punctuation with no surrounding spaces (`word -- word`). `dash-spacing` covers spaced `--` and `---` only.
- A semicolon that precedes a space but does not end a clause. `style.tex` groups this with abbreviation spacing; `abbrev-space` covers the configured abbreviation list only.

### Tests

Each error and warning has a fixture that triggers it and a fixture that must stay clean. Bibliography rules use a small `.bib` fixture. `style.tex` is a parser fixture for ignored `\verb` material and for the known affiliation dash exception. It is not the zero-diagnostic fixture.

## Consequences

- A forgotten tie after an ordinary noun (`result \cite{key}`) is reported as `cite-sentence-role`. That over-reports the case where the author meant a parenthetical citation and missed the `~`. The space test is defined that way on purpose.
- `see~\cite{key}`, `in~\cite{key}`, and `(see \cite{key})` are reported. `(see, e.g.,~\cite{key})` is not.
- The spacing rule and the sentence-role rule propose different repairs. They must not both fire on the same `\cite`.
- Rules that need math mode share one tracker. Warning-tier math checks wait on tests for that tracker.
- ChkTeX is a source of abbreviation-list experience for `abbrev-space`. It is not the implementation and not the dash authority: paperlint’s dash rules are the ones in `style.tex`.
- `refcite-missing` reports keys that `\refcite` and `\refscite` pass through to `\cite`, so the check does not require a LaTeX run. Keys of a bare `\cite` are left to the compiler.
- Duplicate `eprint`, `doi`, and `url` values are literal after the whitespace and brace normalization above. Equivalent identifiers spelled differently are left alone.

## Alternatives considered

- Treating `\cite` inside parentheses or brackets as already parenthetical. Rejected. Sentence role is independent of parentheses.
- Repairing a breakable space before `\cite` by changing it to `~`. Rejected for sentence-role sites. The result, `see~\cite{key}`, keeps the wrong role.
- Excluding `Ref.` and `Refs.` so a hand-rolled “Ref.~\cite” would pass. Rejected. Those words are triggers for the generic `\refcite` / `\refscite` diagnostic.
- Repairing `\cite{key}'s` by suggesting `\refcite{key}'s`. Rejected. The possessive form is its own diagnostic, and the repair is a rephrase.
- Using a following verb as proof that `\cite` is the subject. Rejected for now as too noisy beside parenthetical citations.
- Basing the checker on ChkTeX. Rejected. The citation, `\cref`, `\qty`, and `multline` rules need the mode model above, and ChkTeX’s dash advice disagrees with `style.tex`.
- Flagging every `array`, every power of ten, or an 80-column limit outside display math. Rejected. Each of those contradicts a legal pattern in `style.tex`.
