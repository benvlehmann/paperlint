from __future__ import annotations

import re
from pathlib import Path

from paperlint.config import Config
from paperlint.document import Document, LineRec, Token

DISABLE_RE = re.compile(
    r"paperlint:\s*disable\s*=\s*([A-Za-z0-9_, \-]+)"
)

MATH_ENVS = {
    "equation", "equation*",
    "multline", "multline*",
    "align", "align*",
    "gather", "gather*",
    "cases", "cases*",
    "eqnarray", "eqnarray*",
    "alignat", "alignat*",
    "flalign", "flalign*",
    "split", "split*",
    "aligned", "aligned*",
    "gathered", "gathered*",
}

LIMIT_ENVS = {"equation", "equation*", "multline", "multline*"}

SKIP_ENVS = {"verbatim", "Verbatim", "lstlisting", "minted", "comment"}

SECTIONING = {
    "section", "subsection", "subsubsection", "paragraph", "subparagraph",
}

PROSE_COMMANDS = {
    "text", "intertext", "shortintertext", "mbox",
    "textnormal", "textbf", "textit", "textrm",
}

CITE_COMMANDS = {"cite", "refcite", "refscite"}

RAW_ARG_COMMANDS = {
    "label", "ref", "eqref", "cref", "Cref",
    "bibliography", "addbibresource",
    "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathbb",
    "num", "qty",
}

DEFINITION_COMMANDS = {
    "newcommand", "newcommand*",
    "renewcommand", "renewcommand*",
    "newenvironment", "newenvironment*",
    "renewenvironment", "renewenvironment*",
}

SENTENCE_RELEVANT = {"word", "number", "command", "display_open"}


def load_document(path: Path, config: Config) -> Document:
    document = Document()
    state = _State(document, config)
    _Scanner(path.resolve(), state).run()
    return document


class _State:
    def __init__(self, document: Document, config: Config) -> None:
        self.document = document
        self.config = config
        self.mode_stack = ["text"]
        self.envs: list[str] = []
        self.sectioning: str | None = None
        self.pending_sentence = True
        self.brace_depth = 0
        self.delims: list[str] = []
        self.limit_depth = 0
        self.limit_pending = 0
        self.visiting: list[Path] = []

    @property
    def mode(self) -> str:
        return self.mode_stack[-1]

    def push_mode(self, mode: str) -> None:
        self.mode_stack.append(mode)

    def pop_mode(self) -> None:
        if len(self.mode_stack) > 1:
            self.mode_stack.pop()


class _Scanner:
    def __init__(self, path: Path, state: _State) -> None:
        self.path = path
        self.state = state
        text = path.read_text(encoding="utf-8")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.s = text
        state.document.sources[path] = text
        self.raw_lines = text.splitlines()
        self.i = 0
        self.line = 1
        self.col = 1
        self._recorded: set[int] = set()

    def run(self) -> None:
        if self.path in self.state.visiting:
            return
        self.state.visiting.append(self.path)
        try:
            while self.i < len(self.s):
                self.scan_one()
        finally:
            self._record_line(self.line, self.state.limit_depth > 0)
            self.state.visiting.pop()

    def peek(self, n: int = 0) -> str:
        index = self.i + n
        if index < 0 or index >= len(self.s):
            return ""
        return self.s[index]

    def advance(self) -> None:
        if self.i >= len(self.s):
            return
        char = self.s[self.i]
        self.i += 1
        if char == "\n":
            inside = self.state.limit_depth > 0
            self._record_line(self.line, inside)
            self.state.limit_depth += self.state.limit_pending
            self.state.limit_pending = 0
            self.line += 1
            self.col = 1
        else:
            self.col += 1

    def _record_line(self, number: int, inside: bool) -> None:
        if number in self._recorded or number < 1 or number > len(self.raw_lines):
            return
        self._recorded.add(number)
        text = self.raw_lines[number - 1]
        self.state.document.lines.append(
            LineRec(self.path, number, text, inside)
        )

    def next_line_is_blank(self) -> bool:
        j = self.i + 1
        if j >= len(self.s):
            return False
        while j < len(self.s) and self.s[j] in (" ", "\t"):
            j += 1
        return j >= len(self.s) or self.s[j] == "\n"

    def peek_significant(self) -> str:
        j = self.i
        s = self.s
        while j < len(s):
            if s[j] in (" ", "\t", "\n"):
                j += 1
                continue
            if s[j] == "%":
                j += 1
                while j < len(s) and s[j] != "\n":
                    j += 1
                continue
            return s[j]
        return ""

    def skip_filler(self) -> None:
        while self.i < len(self.s):
            char = self.peek()
            if char in (" ", "\t", "\n"):
                self.advance()
            elif char == "%":
                self.scan_comment()
            else:
                return

    def scan_one(self) -> None:
        char = self.peek()
        if char == "":
            return
        if char == "%":
            self.scan_comment()
            return
        if char == "\\":
            self.scan_backslash()
            return
        if char == "$":
            self.scan_dollar()
            return
        if char in (" ", "\t"):
            self._emit("space", " ")
            while self.peek() in (" ", "\t"):
                self.advance()
            return
        if char == "\n":
            self.scan_newline()
            return
        if char == "~":
            self._emit("nbsp", "~")
            self.advance()
            return
        if char == "{":
            self._emit("punct", "{")
            self.state.brace_depth += 1
            self.advance()
            return
        if char == "}":
            self._emit("punct", "}")
            self.state.brace_depth = max(0, self.state.brace_depth - 1)
            self.advance()
            return
        if char.isalpha():
            self.scan_word()
            return
        if char.isdigit():
            self.scan_number()
            return
        if char == "-":
            self.scan_dash()
            return
        self._emit("punct", char)
        self.advance()

    def scan_comment(self) -> None:
        start = self.i
        self.advance()
        while self.peek() not in {"", "\n"}:
            self.advance()
        comment = self.s[start:self.i]
        match = DISABLE_RE.search(comment)
        if match:
            ids = {part.strip() for part in match.group(1).split(",") if part.strip()}
            key = (self.path, self.line)
            self.state.document.suppressions.setdefault(key, set()).update(ids)
        if self.peek() == "\n":
            self.advance()

    def scan_newline(self) -> None:
        if self.next_line_is_blank():
            self._emit("par", "\n\n")
            self.advance()
            while self.peek() in (" ", "\t"):
                self.advance()
            if self.peek() == "\n":
                self.advance()
            while True:
                j = self.i
                while j < len(self.s) and self.s[j] in (" ", "\t"):
                    j += 1
                if j < len(self.s) and self.s[j] == "\n":
                    while self.peek() in (" ", "\t"):
                        self.advance()
                    if self.peek() == "\n":
                        self.advance()
                    continue
                break
        else:
            self._emit("space", "\n")
            self.advance()

    def scan_dollar(self) -> None:
        if self.peek(1) == "$":
            line, col = self.line, self.col
            self.advance()
            self.advance()
            self._toggle_delim("$$", "display", line, col)
            return
        line, col = self.line, self.col
        self.advance()
        self._toggle_delim("$", "inline", line, col)

    def _toggle_delim(self, delim: str, mode: str, line: int, col: int) -> None:
        closer_to_opener = {"\\]": "\\[", "\\)": "\\(", "$": "$", "$$": "$$"}
        if (
            self.state.delims
            and closer_to_opener.get(delim) == self.state.delims[-1]
        ):
            self.state.delims.pop()
            self.state.pop_mode()
            kind = "display_close" if mode == "display" else "math_shift"
            self._emit(kind, delim, line=line, col=col)
            return
        if delim in {"\\]", "\\)"}:
            self._emit("punct", delim, line=line, col=col)
            return
        self.state.delims.append(delim)
        self.state.push_mode(mode)
        kind = "display_open" if mode == "display" else "math_shift"
        self._emit(kind, delim, line=line, col=col)

    def scan_backslash(self) -> None:
        line, col = self.line, self.col
        if self.s.startswith("\\\\", self.i):
            self.advance()
            self.advance()
            token = self._emit("command", "\\\\", name="\\\\", line=line, col=col)
            token.end_offset = self.i
            return
        if self.s.startswith("\\[", self.i):
            self.advance()
            self.advance()
            self._toggle_delim("\\[", "display", line, col)
            return
        if self.s.startswith("\\]", self.i):
            self.advance()
            self.advance()
            self._toggle_delim("\\]", "display", line, col)
            return
        if self.s.startswith("\\(", self.i):
            self.advance()
            self.advance()
            self._toggle_delim("\\(", "inline", line, col)
            return
        if self.s.startswith("\\)", self.i):
            self.advance()
            self.advance()
            self._toggle_delim("\\)", "inline", line, col)
            return
        self.advance()
        if self.peek() == "":
            return
        if self.peek().isalpha():
            chars: list[str] = []
            while self.peek().isalpha():
                chars.append(self.peek())
                self.advance()
            name = "".join(chars)
            if self.peek() == "*":
                name += "*"
                self.advance()
            letter = True
        else:
            name = self.peek()
            self.advance()
            letter = False
        if name in {"verb", "verb*"}:
            self._consume_verb()
            self._emit("command", "\\" + name, name=name, line=line, col=col)
            return
        if name == " ":
            self._emit("control_space", "\\ ", line=line, col=col)
            return
        token = self._emit("command", "\\" + name, name=name, line=line, col=col)
        base = name[:-1] if name.endswith("*") else name
        if base in SECTIONING:
            self.state.sectioning = base
        self._attach(token, letter)
        token.end_offset = self.i

    def _consume_verb(self) -> None:
        if self.peek() == "" or self.peek().isspace():
            return
        delim = self.peek()
        self.advance()
        while self.peek() not in {"", delim}:
            self.advance()
        if self.peek() == delim:
            self.advance()

    def _attach(self, token: Token, letter: bool) -> None:
        name = token.name
        if name in CITE_COMMANDS:
            self._attach_cite(token)
            return
        if name in {"input", "include"}:
            self._attach_input(token)
            return
        if name in DEFINITION_COMMANDS:
            self._attach_definition(token)
            return
        if name == "begin":
            self._attach_begin(token)
            return
        if name == "end":
            self._attach_end(token)
            return
        if name == "footnote":
            self._attach_footnote(token)
            return
        if name in PROSE_COMMANDS:
            if self.peek_significant() == "{":
                self.skip_filler()
                self._scan_prose_group()
            elif letter:
                self._eat_control_word_space()
            return
        if name in RAW_ARG_COMMANDS or name == "qty":
            self._attach_raw_mandatory(token, letter)
            return
        if letter:
            self._eat_control_word_space()

    def _attach_cite(self, token: Token) -> None:
        options: list[str] = []
        while self.peek_significant() == "[":
            self.skip_filler()
            options.append(self._read_raw("[", "]"))
        if self.peek_significant() == "{":
            self.skip_filler()
            token.mandatory = (self._read_raw("{", "}"),)
        token.optional = tuple(options)
        token.end_offset = self.i

    def _attach_raw_mandatory(self, token: Token, letter: bool) -> None:
        groups: list[str] = []
        while self.peek_significant() == "{":
            self.skip_filler()
            groups.append(self._read_raw("{", "}"))
            if token.name != "qty":
                break
            if len(groups) == 2:
                break
        if groups:
            token.mandatory = tuple(groups)
            self._note_bibliography(token)
        elif letter:
            self._eat_control_word_space()
        token.end_offset = self.i

    def _note_bibliography(self, token: Token) -> None:
        if not token.mandatory:
            return
        if token.name == "bibliography":
            for part in token.mandatory[0].split(","):
                path = resolve_bib(self.path.parent, part, add_extension=True)
                if path is not None:
                    self.state.document.bib_paths.append(path)
        elif token.name == "addbibresource":
            path = resolve_bib(self.path.parent, token.mandatory[0], add_extension=True)
            if path is not None:
                self.state.document.bib_paths.append(path)

    def _attach_input(self, token: Token) -> None:
        filename = ""
        if self.peek_significant() == "{":
            self.skip_filler()
            filename = self._read_raw("{", "}")
        elif self.peek() not in {"", " ", "\t", "\n", "%"}:
            chars: list[str] = []
            while self.peek() not in {"", " ", "\t", "\n", "%"}:
                chars.append(self.peek())
                self.advance()
            filename = "".join(chars)
        token.mandatory = (filename,)
        token.end_offset = self.i
        self._include(filename)
        if _name_is_word(token.name):
            self._eat_control_word_space()

    def _include(self, filename: str) -> None:
        path = _resolve_tex(self.path.parent, filename)
        if path is None:
            return
        if path.suffix in {".bbl", ".aux"}:
            return
        _Scanner(path, self.state).run()

    def _attach_definition(self, token: Token) -> None:
        is_env = token.name.startswith("newenvironment") or token.name.startswith(
            "renewenvironment"
        )
        if self.peek_significant() == "{":
            self.skip_filler()
            self._read_raw("{", "}")
        elif not is_env and self.peek() == "\\":
            self.advance()
            while self.peek().isalpha():
                self.advance()
            if self.peek() == "*":
                self.advance()
        if self.peek_significant() == "[":
            self.skip_filler()
            self._read_raw("[", "]")
            if self.peek_significant() == "[":
                self.skip_filler()
                self._read_raw("[", "]")
        bodies: list[str] = []
        count = 2 if is_env else 1
        for _ in range(count):
            if self.peek_significant() != "{":
                break
            self.skip_filler()
            bodies.append(self._read_raw("{", "}"))
        token.mandatory = tuple(bodies)
        token.end_offset = self.i

    def _attach_begin(self, token: Token) -> None:
        if self.peek_significant() != "{":
            return
        self.skip_filler()
        env = self._read_raw("{", "}").strip()
        token.mandatory = (env,)
        if env in SKIP_ENVS:
            token.end_offset = self.i
            self._skip_environment(env)
            return
        base = env[:-1] if env.endswith("*") else env
        if env in {"figure", "figure*"}:
            if self.peek_significant() == "[":
                self.skip_filler()
                token.optional = (self._read_raw("[", "]"),)
        elif base in {"tabular", "array"}:
            if self.peek_significant() == "[":
                self.skip_filler()
                self._read_raw("[", "]")
            if env == "tabular*":
                if self.peek_significant() == "{":
                    self.skip_filler()
                    self._read_raw("{", "}")
            if self.peek_significant() == "{":
                self.skip_filler()
                token.preamble = self._read_raw("{", "}")
        token.end_offset = self.i
        self.state.envs.append(env)
        if env in MATH_ENVS:
            self.state.push_mode("display")
        if env in LIMIT_ENVS:
            self.state.limit_pending += 1

    def _attach_end(self, token: Token) -> None:
        if self.peek_significant() != "{":
            return
        self.skip_filler()
        env = self._read_raw("{", "}").strip()
        token.mandatory = (env,)
        token.end_offset = self.i
        if env == "document":
            self.i = len(self.s)
            return
        if env not in self.state.envs:
            return
        while self.state.envs:
            closed = self.state.envs.pop()
            if closed in MATH_ENVS:
                self.state.pop_mode()
            if closed in LIMIT_ENVS:
                if self.state.limit_depth > 0:
                    self.state.limit_depth -= 1
                elif self.state.limit_pending > 0:
                    self.state.limit_pending -= 1
            if closed == env:
                break

    def _attach_footnote(self, token: Token) -> None:
        if self.peek_significant() == "[":
            self.skip_filler()
            token.optional = (self._read_raw("[", "]"),)
        if self.peek_significant() == "{":
            self.skip_filler()
            self._scan_prose_group()
        token.end_offset = self.i

    def _scan_prose_group(self) -> None:
        self.state.push_mode("text")
        base = self.state.brace_depth
        self.scan_one()
        while self.i < len(self.s) and self.state.brace_depth > base:
            self.scan_one()
        self.state.pop_mode()

    def _skip_environment(self, name: str) -> None:
        closer = "\\end{" + name + "}"
        while self.i < len(self.s):
            if self.s.startswith(closer, self.i):
                for _ in range(len(closer)):
                    self.advance()
                return
            self.advance()

    def _read_raw(self, open_char: str, close_char: str) -> str:
        if self.peek() != open_char:
            return ""
        self.advance()
        start = self.i
        depth = 1
        while self.i < len(self.s) and depth:
            char = self.peek()
            if char == "\\":
                self.advance()
                if self.peek() != "":
                    self.advance()
                continue
            if char == "%":
                self.scan_comment()
                continue
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    inner = self.s[start:self.i]
                    self.advance()
                    return inner
            self.advance()
        return self.s[start:self.i]

    def _eat_control_word_space(self) -> None:
        while self.peek() in (" ", "\t"):
            self.advance()
        if self.peek() == "\n" and not self.next_line_is_blank():
            self.advance()

    def scan_word(self) -> None:
        line, col = self.line, self.col
        start = self.i
        while self.peek().isalpha():
            self.advance()
        while self.peek() == ".":
            if self.peek(1).isalpha():
                self.advance()
                while self.peek().isalpha():
                    self.advance()
                continue
            tentative = self.s[start:self.i + 1]
            if tentative.casefold() in self.state.config.abbreviations:
                self.advance()
            break
        self._emit("word", self.s[start:self.i], line=line, col=col)

    def scan_number(self) -> None:
        line, col = self.line, self.col
        start = self.i
        while self.peek().isdigit():
            self.advance()
        if self.peek() == "." and self.peek(1).isdigit():
            self.advance()
            while self.peek().isdigit():
                self.advance()
        if self.peek() in "eE":
            sign = self.peek(1)
            digit_at = 2 if sign in "+-" else 1
            if self.peek(digit_at).isdigit():
                self.advance()
                if self.peek() in "+-":
                    self.advance()
                while self.peek().isdigit():
                    self.advance()
        self._emit("number", self.s[start:self.i], line=line, col=col)

    def scan_dash(self) -> None:
        if self.s.startswith("---", self.i):
            text = "---"
        elif self.s.startswith("--", self.i):
            text = "--"
        else:
            text = "-"
        self._emit("punct", text)
        for _ in text:
            self.advance()

    def _emit(
        self,
        kind: str,
        text: str,
        name: str = "",
        line: int | None = None,
        col: int | None = None,
    ) -> Token:
        at_start = False
        mode = self.state.mode
        if (
            kind in SENTENCE_RELEVANT
            and self.state.pending_sentence
            and mode == "text"
        ):
            at_start = True
            self.state.pending_sentence = False
        if kind == "punct" and text in ".!?" and mode == "text":
            self.state.pending_sentence = True
        if kind == "par":
            self.state.pending_sentence = True
        token = Token(
            kind=kind,
            text=text,
            file=self.path,
            line=self.line if line is None else line,
            col=self.col if col is None else col,
            mode=mode,
            envs=tuple(self.state.envs),
            sectioning=self.state.sectioning,
            at_sentence_start=at_start,
            name=name,
        )
        self.state.document.tokens.append(token)
        return token


def _name_is_word(name: str) -> bool:
    base = name[:-1] if name.endswith("*") else name
    return base.isalpha()


def _resolve_tex(directory: Path, name: str) -> Path | None:
    cleaned = name.strip().strip('"').strip("'")
    if not cleaned:
        return None
    path = Path(cleaned)
    if path.suffix == "":
        path = path.with_suffix(".tex")
    if path.suffix in {".bbl", ".aux"}:
        return None
    if not path.is_absolute():
        path = directory / path
    path = path.resolve()
    if path.suffix in {".bbl", ".aux"} or not path.is_file():
        return None
    return path


def resolve_bib(directory: Path, name: str, add_extension: bool) -> Path | None:
    cleaned = name.strip().strip('"').strip("'")
    if not cleaned:
        return None
    path = Path(cleaned)
    if add_extension and path.suffix == "":
        path = path.with_suffix(".bib")
    if not path.is_absolute():
        path = directory / path
    return path.resolve()
