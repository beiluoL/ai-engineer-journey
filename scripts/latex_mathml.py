#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
latex_mathml.py —— 构建期 LaTeX → MathML 转换（零运行时依赖）。

为什么自己写而不用 KaTeX / MathJax：
    仓库的 HTML 是「零外部依赖、双击即开」的产物。接 CDN 会断网即残；
    自带 KaTeX 要往仓库里搬 ~20 个 woff2 字体（约 300 KB），还破坏「只镜像
    .html」的现有产物树约定。MathML Core 是浏览器原生的数学排版方言，
    构建期算完、运行时不管，正好对上仓库的设计目标。

覆盖范围（以 llm-fundamentals 全部 9 篇文档实际用到的语法为准）：
    · 分数 / 根式（含 n 次根）/ 上下标 / 分组 / 定界符（\\left \\right \\big…）
    · \\text{} 中文混排、\\operatorname{}、\\mathbb \\mathcal \\mathbf \\mathrm \\mathfrak
    · \\sum \\prod \\int 的上下限、\\underbrace \\overbrace \\boxed \\hat \\vec \\bar
    · 矩阵环境 bmatrix/Bmatrix/pmatrix/matrix/vmatrix、cases、aligned
    · 间距 \\, \\: \\! \\quad \\qquad；箭头 \\to \\Longrightarrow \\xrightarrow
    · 希腊字母与常用数学符号

退化策略：遇到不认识的命令**不静默吞掉** —— 记进 unknown 列表（构建期会打印），
        同时按字面输出，宁可丑也不会变成乱码/空白。

用法：
    from latex_mathml import render_math
    body, unknown = render_math(r"\\text{logits} = h \\, W_{lm}", display=True)
"""

from __future__ import annotations

import html
import re

__all__ = ["LatexError", "render_math", "scan_source"]


class LatexError(Exception):
    """公式语法异常（括号不成对等）。"""


# ----------------------------------------------------------------------------
# 小工具
# ----------------------------------------------------------------------------

def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _mo(s: str, **attrs) -> str:
    a = "".join(' %s="%s"' % (k, v) for k, v in attrs.items())
    return "<mo%s>%s</mo>" % (a, _esc(s))


def _mi(s: str, **attrs) -> str:
    a = "".join(' %s="%s"' % (k, v) for k, v in attrs.items())
    return "<mi%s>%s</mi>" % (a, _esc(s))


def _mn(s: str) -> str:
    return "<mn>%s</mn>" % _esc(s)


def _mtext(s: str, cls: str = "") -> str:
    """文字节点。cls="tx" 标记 \\text{} 里的「正文类文字」——中文只在正文字体
    里才有字形（STIX Two Math 这类数学字体不含 CJK），页面据此换成正文栈，
    免得 \\text{注意力} 掉进衬线中文、跟周围正文的苹方/黑体对不上。"""
    a = ' class="%s"' % cls if cls else ""
    return "<mtext%s>%s</mtext>" % (a, _esc(s))


def _mrow(*parts) -> str:
    return "<mrow>" + "".join(parts) + "</mrow>"


def _mspace(w: str) -> str:
    return '<mspace width="%s"/>' % w


def _delim(ch: str, size: str | None = None) -> str:
    """定界符：可拉伸的用小 mo 让它撑开，普通括号禁止拉伸免得挤成一条。"""
    stretchy = set("()[]{}|‖⟨⟩/\\")
    attrs = {"stretchy": "true" if ch in stretchy else "false"}
    if size:
        attrs["maxsize"] = size
        attrs["minsize"] = size
    return _mo(ch, **attrs)


def _variant(ch, variant: str) -> str:
    """数学字母：靠 mathvariant 变换出黑体/花体/粗体，内容保持普通字母。"""
    if len(ch) != 1:
        return _mi(ch)
    return _mi(ch, mathvariant=variant)


# ----------------------------------------------------------------------------
# 符号表
# ----------------------------------------------------------------------------

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "varkappa": "ϰ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ",
    "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "ϕ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ",
    "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

FONTS = {
    "mathbb": "double-struck", "mathbbm": "double-struck",
    "mathcal": "script", "mathscr": "script",
    "mathfrak": "fraktur",
    "mathbf": "bold", "boldsymbol": "bold", "bm": "bold",
    "mathit": "italic", "it": "italic",
    "mathsf": "sans-serif", "mathtt": "monospace",
    "mathrm": "normal", "textrm": "normal", "textbf": "normal",
}

LOG_LIKE = {
    "log": "log", "ln": "ln", "lg": "lg", "exp": "exp",
    "sin": "sin", "cos": "cos", "tan": "tan", "cot": "cot",
    "sec": "sec", "csc": "csc",
    "arcsin": "arcsin", "arccos": "arccos", "arctan": "arctan",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "max": "max", "min": "min", "sup": "sup", "inf": "inf",
    "lim": "lim", "liminf": "lim‾", "limsup": "lim‾",
    "det": "det", "gcd": "gcd", "lcm": "lcm", "Pr": "Pr",
    "arg": "arg", "deg": "deg", "dim": "dim", "ker": "ker", "hom": "hom",
    "mathbb{E}": "E",
}

SYM_OPS = {
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓",
    "odot": "⊙", "otimes": "⊗", "oplus": "⊕", "ominus": "∓",
    "ast": "∗", "star": "⋆", "circ": "∘", "bullet": "•",
    "cap": "∩", "cup": "∪", "sqcap": "⊓", "sqcup": "⊔",
    "wedge": "∧", "vee": "∨", "setminus": "∖", "amalg": "⨿",
    "leq": "≤", "le": "≤", "leqq": "≦",
    "geq": "≥", "ge": "≥", "geqq": "≧",
    "neq": "≠", "ne": "≠", "approx": "≈", "equiv": "≡",
    "sim": "∼", "simeq": "≃", "cong": "≅", "propto": "∝",
    "ll": "≪", "gg": "≫", "prec": "≺", "succ": "≻",
    "preceq": "⪯", "succeq": "⪰",
    "subset": "⊂", "supset": "⊃", "subseteq": "⊆", "supseteq": "⊇",
    "sqsubseteq": "⊑", "sqsupseteq": "⊒",
    "in": "∈", "notin": "∉", "ni": "∋", "mid": "∣", "parallel": "∥",
    "vdash": "⊢", "models": "⊨",
    "Rightarrow": "⇒", "Leftarrow": "←", "Leftrightarrow": "⇔",
    "mapsto": "↦", "longmapsto": "↦", "longleftarrow": "⇐",
    "uparrow": "↑", "downarrow": "↓", "updownarrow": "↕",
    "Uparrow": "⇑", "Downarrow": "⇓",
    "rightarrow": "→", "to": "→", "leftarrow": "←", "gets": "←",
    "Longrightarrow": "⟹", "Longleftarrow": "⟸", "Longleftrightarrow": "⟺",
    "leadsto": "⇝", "rightsquigarrow": "⇢",
}

SYM_REL = {
    "ldots": "…", "dots": "…", "vdots": "⋮", "ddots": "⋱",
    "langle": "⟨", "rangle": "⟩", "lbrace": "{", "rbrace": "}",
    "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
    "vert": "|", "Vert": "‖", "lvert": "|", "rvert": "|",
    "norm": "‖", "angle": "∠", "degree": "°", "hbar": "ℏ",
    "ell": "ℓ", "aleph": "ℵ", "wp": "℘", "Re": "ℜ", "Im": "ℑ",
    "emptyset": "∅", "varnothing": "∅", "forall": "∀", "exists": "∃",
    "neg": "¬", "top": "⊤", "bot": "⊥",
    "infty": "∞", "partial": "∂", "nabla": "∇", "prime": "′",
}

BIG_OPS = {
    "sum": "∑", "prod": "∏", "coprod": "∐", "int": "∫",
    "oint": "∮", "oiint": "∬", "oiiint": "∭",
    "bigcap": "⋂", "bigcup": "⋃",
    "bigoplus": "⨁", "bigotimes": "⊗", "bigodot": "⊙",
    "bigvee": "⋁", "bigwedge": "⋀",
}

SPACING = {
    ",": "3pt", ":": "4pt", ";": "5pt", "!": "-3pt",
    "quad": "1em", "qquad": "2em", "enspace": "0.5em",
    "thinspace": "3pt", "negthinspace": "-3pt",
    "medspace": "4pt", "negmedspace": "-4pt",
    "thickspace": "5pt", "negthickspace": "-5pt",
}

BIG_DELIM_SIZE = {
    "big": "1.3em", "Big": "1.7em", "bigg": "2.2em", "Bigg": "2.9em",
    "bigl": "1.3em", "bigr": "1.3em", "Bigl": "1.7em", "Bigr": "1.7em",
    "biggl": "2.2em", "biggr": "2.2em", "Biggl": "2.9em", "Biggr": "2.9em",
}

DELIM_LITERAL = {
    "(": "(", ")": ")", "[": "[", "]": "]",
    "{": "{", "}": "}", "|": "|", "\\|": "‖",
    "langle": "⟨", "rangle": "⟩", "lbrace": "{", "rbrace": "}",
    "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
    "vert": "|", "Vert": "‖", "lVert": "‖", "rVert": "‖",
    "lvert": "|", "rvert": "|", "/": "/", "backslash": "\\",
    "uparrow": "↑", "downarrow": "↓", "updownarrow": "↕",
}

ACCENTS = {
    "hat": "^", "widehat": "^", "check": "ˇ", "tilde": "~",
    "widetilde": "~", "bar": "‾", "overline": "‾",
    "vec": "→", "dot": "˙", "ddot": "¨", "acute": "´", "grave": "`",
}

_ENV_NAME = (r"(bmatrix|Bmatrix|pmatrix|vmatrix|Vmatrix|matrix|smallmatrix|"
             r"cases|aligned|alignedat|gather|gathered|split|array)")


# ----------------------------------------------------------------------------
# 后处理
# ----------------------------------------------------------------------------

_CLOSERS = ")]}⟩‖⌋⌉|"
_OPENERS = "([{⟨⌊⌈|"

def _wrap_mrow(mml: str) -> str:
    """上下标只有一个元素时保持原样，多个并排元素则包进 mrow。

    MathML Core 其实允许 msub/msup 里写多个子节点（其余自动视作 mrow），
    但显式包一层结构更明确，也避免不同浏览器对隐含 mrow 的处理差异。
    """
    depth, i, n, top = 0, 0, len(mml), 0
    while i < n:
        if mml[i] != "<":
            i += 1
            continue
        j = mml.find(">", i)
        if j < 0:
            break
        tag = mml[i + 1:j]
        if not tag.endswith("/"):
            depth += -1 if tag.startswith("/") else 1
            if depth == 0:
                top += 1
                if top > 1:
                    return "<mrow>" + mml + "</mrow>"
        i = j + 1
    return mml


# 上下标挂在「右定界符」上时，MathML 形如 <msub><mo>)</mo><mi>i</mi></msub>——
# 定界符是 msub 的**底数**，不是它的前驱。模式要按这个结构来写。
# 注意写成 <m(sub|sup|subsup)>，不要写成 <ms(sub|...)>——后者拼起来是字面
# "<mssub>"，re 的 prefix 优化会据此要求输入里真出现 "<mssub>"，永远匹配不上。
_RE_HANG = re.compile(
    r"<m(?P<k>sub|sup|subsup)>"
    r"(?P<base><mo[^>]*>[" + re.escape(_CLOSERS) + r"]</mo>)"
    r"(?P<rest>.*?)</m(?P=k)>", re.S)


def hoist_close_scripts(mml: str) -> str:
    """把错挂在右定界符上的上下标，改挂到整个「左定界符…右定界符」分组上。

    例：`\\operatorname{softmax}(z)_i` 的 `_i` 本该作用于整个 softmax(z)，
    逐原子解析却会让它挂到右括号 `)` 上，语义读成「右括号的第 i 项」。
    这里取该右定界符之前最近的左定界符，把两者之间整段包成 mrow 当底数。

    倒序处理：每次替换只发生在当前匹配之前的位置之后，前面的下标不会失效。
    """
    for m in reversed(list(_RE_HANG.finditer(mml))):
        head = mml[:m.start()]
        opener = None
        for cand in re.finditer(r"<mo[^>]*>[" + re.escape(_OPENERS) + r"]</mo>", head):
            opener = cand      # 取最后一个：就近配对的左定界符才是对的
        if opener is None:
            continue
        # 右括号是被包在它自己的 <msub> 里的，所以不能整段切到它的 </mo>：
        # 那段会带上外层 <msub> 的开标签，拼出不配对的标签。
        # 正确取法 = [左定界符 …) + 右定界符本体。
        base_start = opener.start()
        # softmax(z)_i 的底数该是整个 softmax(z) 而非只有 (z)：
        # 紧贴在左定界符前的 \operatorname{}（渲染成 mtext）顺手吸收进来。
        fn = re.search(r"<mtext>[^<]*</mtext>\Z", head[:base_start])
        if fn:
            base_start = fn.start()
        base = mml[base_start:m.start()] + m.group("base")
        kind = m.group("k")
        mml = (mml[:base_start]
               + "<m" + kind + "><mrow>" + base + "</mrow>"
               + m.group("rest") + "</m" + kind + ">"
               + mml[m.end():])
    return mml


# ----------------------------------------------------------------------------
# 解析器
# ----------------------------------------------------------------------------

class Parser:
    """递归下降：表达式 → MathML 片段字符串。"""

    def __init__(self, src: str, display: bool = False, unknown: list | None = None):
        self.s = src
        self.i = 0
        self.display = display
        self.unknown = unknown if unknown is not None else []

    # ---- 游标 ----
    def rest(self) -> str:
        return self.s[self.i:]

    def peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.s[j] if j < len(self.s) else ""

    def skip_ws(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in " \t\n\r":
            self.i += 1

    def _missing(self, name: str) -> None:
        if name not in self.unknown:
            self.unknown.append(name)

    # ---- 入口 ----
    def parse(self) -> str:
        self.skip_ws()
        parts = []
        while self.i < len(self.s):
            part = self.parse_sequence_item()
            if not part:
                break
            parts.append(part)
        return hoist_close_scripts("".join(parts))

    def parse_sequence_item(self) -> str:
        """一个原子 + 它后面挂的 _ / ^ 后缀。"""
        self.skip_ws()
        if self.i >= len(self.s):
            return ""
        atom = self.parse_atom()
        if not atom:
            return ""
        return self.parse_scripts(atom)

    def parse_atom(self) -> str:
        c = self.peek()
        if c == "{":
            return self.parse_group()
        if c == "}":
            # 多余的右括号：跳过而不是崩掉（源文偶有手写残留）
            self.i += 1
            return ""
        if c == "\\":
            return self.parse_command()
        if c in "_^":
            # 缺底数的孤立上下标：当普通字符显示，不至于吞掉内容
            self.i += 1
            return _mi(c)
        if c in "+-=<>*|/:?":
            self.i += 1
            return _mo(c)
        if c == "~":
            self.i += 1
            return _mspace("1em")
        if c.isdigit():
            self.i += 1
            return _mn(c)
        if c.isalpha():
            self.i += 1
            return _mi(c)
        if c in "()[]|":
            self.i += 1
            return _delim(c)
        # 其余（含中文）：交给页面字体渲染
        self.i += 1
        return _mi(c)

    # ---- 花括号分组 ----
    def parse_group(self) -> str:
        self.i += 1  # 吃 {
        parts = []
        while self.i < len(self.s):
            c = self.peek()
            if c == "}":
                self.i += 1
                break
            if c == "{":
                parts.append(self.parse_group())
                continue
            if c == "\\" and self.peek(1) == "\\":
                self.i += 2
                parts.append(_mspace("0.5em"))
                continue
            if c == "&":
                self.i += 1
                parts.append(_mspace("0.5em"))
                continue
            parts.append(self.parse_sequence_item())
        return hoist_close_scripts("".join(parts))

    # ---- 读配对花括号内的「原始文本」（给 \text 用） ----
    def read_braced_text(self) -> str:
        """自当前 { 起读到配对 }，返回原始文本；光标停在 } 之后。"""
        depth = 1
        buf = []
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == "\\":
                buf.append(c)
                self.i += 1
                if self.i < len(self.s):
                    buf.append(self.s[self.i])
                    self.i += 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    self.i += 1
                    break
            buf.append(c)
            self.i += 1
        return "".join(buf).strip()

    # ---- 命令 ----
    def parse_command(self) -> str:
        self.i += 1  # 吃 \
        if self.i >= len(self.s):
            return ""
        c = self.peek()

        if not c.isalpha():
            self.i += 1
            # \\; \\! \\, 这类「反斜杠 + 标点」是间距命令，不是运算符
            if c in SPACING:
                return _mspace(SPACING[c])
            if c == "," and self.i < len(self.s) and self.s[self.i] in "0123456789.":
                m = re.match(r"[0-9]+(\.[0-9]+)?", self.s[self.i:])
                if m:
                    self.i += m.end()
                    return _mspace(m.group(0) + "mu")
                return _mspace("3mu")
            if c in "0123456789.":
                return _mspace(c + "pt")
            return self.char_mo(c)

        m = re.match(r"[a-zA-Z]+", self.rest())
        if not m:
            self.i += 1
            return self.char_mo(c)
        name = m.group(0)
        self.i += len(name)
        return self.dispatch(name)

    def char_mo(self, ch: str) -> str:
        mapping = {"{": "{", "}": "}", "|": "‖", "%": "%", "$": "$",
                   "&": "&", "_": "_", "#": "#", "\\": "\\"}
        return _delim(mapping[ch]) if ch in mapping else _mo(ch)

    # ---- 指令分发 ----
    def dispatch(self, name: str) -> str:
        if name in SPACING:
            return _mspace(SPACING[name])
        if name == "hspace":
            self.skip_ws()
            if self.peek() == "{":
                self.i += 1
                m = re.match(r"[0-9.]+", self.read_braced_text())
            else:
                m = re.match(r"[0-9.]+", self.rest())
                if m:
                    self.i += m.end()
            return _mspace((m.group(0) if m else "1") + "em")
        if name in ("hfill", "quad", "qquad"):
            return _mspace("1em" if name == "quad" else "2em")
        if name == "nobreakspace":
            return _mspace("0.25em")

        if name in GREEK:
            return _mi(GREEK[name])
        if name in FONTS:
            return self.parse_font(name)
        if name in ("operatorname", "operatorname*"):
            return _mtext(self.read_brace_or_char())
        if name in ("text", "textrm", "textbf", "textit", "mbox",
                    "textnormal", "texttt", "textsf", "textmd"):
            return _mtext(self.read_brace_or_char(), cls="tx")
        if name in ("xrightarrow", "xleftarrow", "xRightarrow",
                    "xleftarrow"):
            return self.parse_xarrow(name)
        if name in ("underbrace", "overbrace"):
            return self.parse_under_over(name == "overbrace")
        if name == "boxed":
            self.skip_ws()
            inner = self.parse_group() if self.peek() == "{" else self.parse_atom()
            return '<mstyle class="math-boxed">%s</mstyle>' % inner
        if name in ACCENTS:
            self.skip_ws()
            inner = self.parse_group() if self.peek() == "{" else self.parse_atom()
            return _mrow("<mover accent=\"true\">", inner, _mo(ACCENTS[name]),
                         "</mover>")
        if name == "sqrt":
            return self.parse_sqrt()
        if name in ("frac", "dfrac", "tfrac"):
            return self.parse_frac()
        if name == "binom":
            self.skip_ws()
            a = self.parse_group() if self.peek() == "{" else self.parse_atom()
            self.skip_ws()
            b = self.parse_group() if self.peek() == "{" else self.parse_atom()
            return _mrow('<mfrac linethickness="0">', a, b, "</mfrac>")
        if name in ("left", "right"):
            return self.parse_delimiter(name)
        if name in BIG_DELIM_SIZE:
            return self.parse_bigdelim(name)
        if name in LOG_LIKE:
            # 算子名按 LaTeX 语义 upright 显示（\log \max … 不是斜体变量）
            return _mtext(LOG_LIKE[name])
        if name in BIG_OPS:
            return _mo(BIG_OPS[name], movablelimits="true")
        if name in SYM_OPS:
            return _mo(SYM_OPS[name])
        if name in SYM_REL:
            return _mo(SYM_REL[name])
        if name == "begin":
            return self.parse_begin()

        self._missing(name)
        return _mi(name)

    def read_brace_or_char(self) -> str:
        self.skip_ws()
        if self.peek() == "{":
            self.i += 1
            return self.read_braced_text()
        if self.peek():
            ch = self.peek()
            self.i += 1
            return ch
        return ""

    def parse_font(self, name: str) -> str:
        self.skip_ws()
        if self.peek() == "{":
            self.i += 1
            raw = self.read_braced_text()
        elif self.peek():
            raw = self.peek()
            self.i += 1
        else:
            return ""
        if not raw:
            return ""
        if len(raw) == 1:
            return _variant(raw, FONTS[name])
        # 多字符（\mathrm{KL}）：整坨套 mathvariant
        return _mi(raw, mathvariant=FONTS[name])

    def parse_sqrt(self) -> str:
        self.skip_ws()
        opt = ""
        if self.peek() == "[":
            end = self.s.find("]", self.i)
            if end > self.i:
                opt = self.s[self.i + 1:end].strip()
                self.i = end + 1
        self.skip_ws()
        inner = self.parse_group() if self.peek() == "{" else self.parse_read_atom()
        if opt:
            return _mrow("<mroot>", inner, opt, "</mroot>")
        return "<msqrt>%s</msqrt>" % inner

    def parse_frac(self) -> str:
        self.skip_ws()
        num = self.parse_group() if self.peek() == "{" else self.parse_read_atom()
        self.skip_ws()
        den = self.parse_group() if self.peek() == "{" else self.parse_read_atom()
        return _mrow("<mfrac>", num, den, "</mfrac>")

    def parse_read_atom(self) -> str:
        """取一个原子，但不吃它后面的 _ / ^（避免把下标误当分子）。"""
        saved_i = self.i
        atom = self.parse_atom()
        if self.i > saved_i and self.peek() in "_^":
            self.i = saved_i
        return atom

    def parse_delimiter(self, kind: str) -> str:
        """\\left / \\right 后的定界符。命令已消费，这里直接读符号。"""
        self.skip_ws()
        name = self.read_delim_name()
        if name in ("", ".", "left", "right"):
            return '<mo stretchy="true">&#x2009;</mo>'  # 隐形定界符
        return _delim(DELIM_LITERAL.get(name, DELIM_LITERAL.get(name, name)))

    def parse_bigdelim(self, _name: str) -> str:
        size = BIG_DELIM_SIZE[_name]
        self.skip_ws()
        name = self.read_delim_name()
        if name in ("", "."):
            return '<mo stretchy="true">&#x2009;</mo>'
        return _delim(DELIM_LITERAL.get(name, name), size=size)

    def read_delim_name(self) -> str:
        if self.peek() == "\\":
            self.i += 1
            m = re.match(r"[a-zA-Z]+", self.rest())
            if m:
                self.i += m.end()
                return m.group(0)
            if self.peek():
                ch = self.peek()
                self.i += 1
                return ch
            return ""
        if self.peek():
            ch = self.peek()
            self.i += 1
            return ch
        return ""

    def parse_xarrow(self, name: str) -> str:
        """\\xrightarrow{标签}：标签里有 \\text{} 这类命令，必须走解析而不是当纯文本。

        踩过的坑：原来用 read_brace_or_char() 读原文再包 mtext，于是
        `\\xrightarrow{\\text{连续提升}}` 渲染出字面 "\\text{连续提升}"——
        「没认出来就当纯文本」在这里正好把合法命令漏成了伪文本。
        """
        arrow = {"xrightarrow": "⟶", "xleftarrow": "←",
                 "xRightarrow": "⟹"}.get(name, "⟶")
        self.skip_ws()
        if self.peek() == "{":
            label = _wrap_mrow(self.parse_group())
        else:
            label = _wrap_mrow(self.parse_atom())
        return _mrow("<munder movablelimits=\"false\">", _mo(arrow),
                     (label if label else _mspace("0.5em")),
                     "</munder>")

    def parse_under_over(self, over: bool) -> str:
        """\\underbrace{X}_Y / \\overbrace{X}^Y。

        MathML 没有 underbrace 元素，惯用写法是「花括号符号做底、X 在上、Y 在下」：
        <munderover><mo>⏟</mo><mrow>Y</mrow><mrow>X</mrow></munderover>。
        """
        self.skip_ws()
        if self.peek() == "{":
            self.i += 1
            body = self.read_braced_text()
            body = self.parse_rows(body)
        else:
            body = self.parse_atom()
        return _mrow(
            '<munderover accent="true" accentunder="true">',
            '<mo stretchy="true">%s</mo>' % ("⏞" if over else "⏟"),
            _mspace("0pt"), body,
            "</munderover>",
        )

    # ---- 环境 ----
    def parse_begin(self) -> str:
        # 命令已被 parse_command 消费掉 \begin，这里只需匹配 \{env\}
        m = re.match(r"\s*\{" + _ENV_NAME + r"\}", self.rest(), re.S)
        if not m:
            return ""
        env = m.group(1)
        self.i += m.end()
        end_re = re.compile(r"\\end\s*\{\s*" + env + r"\s*\}", re.S)
        em = end_re.search(self.s, self.i)
        if em is None:
            self._missing("end{%s}" % env)
            body = self.s[self.i:]
            self.i = len(self.s)
        else:
            body = self.s[self.i:em.start()]
            self.i = em.end()
        return self.render_env(env, body)

    def render_env(self, env: str, body: str) -> str:
        if env in ("aligned", "alignedat", "gather", "gathered", "split"):
            rows = body.split(r"\\")
            trs = "".join("<mtr><mtd>%s</mtd></mtr>" % self.parse_rows(r)
                          for r in rows)
            return '<mtable columnalign="left">%s</mtable>' % trs

        if env == "cases":
            trs = []
            for r in body.split(r"\\"):
                cells = r.split("&")
                left = self.parse_rows(cells[0])
                right = (self.parse_rows("&".join(cells[1:]))
                         if len(cells) > 1 else "")
                trs.append('<mtr><mtd>%s</mtd><mtd><mo>,</mo></mtd>'
                           '<mtd>%s</mtd></mtr>' % (left, right))
            return '<mtable columnalign="left">%s</mtable>' % "".join(trs)

        delims = {
            "bmatrix": ("[", "]"), "Bmatrix": ("{", "}"),
            "pmatrix": ("(", ")"), "matrix": ("", ""),
            "smallmatrix": ("", ""),
            "vmatrix": ("|", "|"), "Vmatrix": ("‖", "‖"),
        }
        open_d, close_d = delims.get(env, ("", ""))
        trs = "".join(
            "<mtr>%s</mtr>" % "".join(
                "<mtd>%s</mtd>" % self.parse_rows(c) for c in r.split("&"))
            for r in body.split(r"\\")
        )
        table = '<mtable columnspacing="0.7em">%s</mtable>' % trs
        if open_d or close_d:
            return _mrow(_delim(open_d), table, _delim(close_d))
        return _mrow(table)

    def parse_rows(self, src: str) -> str:
        """环境单元格内的一行（可含 _ / ^ 与嵌套命令）。"""
        saved_s, saved_i = self.s, self.i
        self.s, self.i = src, 0
        try:
            return self.parse()
        finally:
            self.s, self.i = saved_s, saved_i

    # ---- 上下标 ----
    def parse_scripts(self, atom: str) -> str:
        is_bigop = any(t in atom for t in ("∑", "∏", "∫", "⋂", "⋃", "∐", "⨁"))
        while self.i < len(self.s):
            self.skip_ws()
            c = self.peek()
            if c not in "_^":
                break
            self.i += 1
            arg = self.parse_argument()
            if is_bigop:
                # 大运算符：上下限分别挂 munder / mover，显示时自动放到上下面
                if c == "_":
                    atom = self._append_limit(atom, "munder", arg)
                else:
                    atom = self._append_limit(atom, "mover", arg)
                continue
            # 上下标参数本身要是一个「整体」：d_{model} 的 model 是 5 个字母，
            # 不包 mrow 就成了 6 个并排子节点，语义上容易被读成 W 后跟一串字母
            atom = ("<msub>%s%s</msub>" % (atom, _wrap_mrow(arg))) if c == "_" \
                else ("<msup>%s%s</msup>" % (atom, _wrap_mrow(arg)))
        return atom

    @staticmethod
    def _append_limit(atom: str, tag: str, arg: str) -> str:
        close = "</%s>" % tag
        if close in atom:
            return atom.replace(close, arg + close)
        return _mrow("<%s movablelimits=\"true\">" % tag, atom, arg, close)

    def parse_argument(self) -> str:
        """`_` / `^` 的参数：花括号整体，否则吃掉后续一整串字母数字。

        LaTeX 里 `W_lm` 等于 `W_{lm}`；只吃一个字符会把 `W_lm` 拆成
        `W_l m`，语义就错了。`parse_group()` 自己负责吃掉 `{`，这里不能再吞。
        """
        self.skip_ws()
        if self.peek() == "{":
            return self.parse_group()
        if self.peek() == "\\":
            return self.parse_command()
        if self.peek() and self.peek() not in "_^":
            m = re.match(r"[A-Za-z0-9]+", self.rest())
            if m:
                self.i += m.end()
                return _mi(m.group(0)) if m.group(0)[-1].isalpha() else _mn(m.group(0))
        return self.parse_atom()


# ----------------------------------------------------------------------------
# 对外接口
# ----------------------------------------------------------------------------

# 出口自检用：数学排版结果里不该再出现「反斜杠命令」或「未配对花括号」。
# 一旦出现，说明某条命令的参数被当纯文本读了（不是不认识的命令，是解析漏了），
# 例如 \xrightarrow{\text{连续提升}} 早期就漏成了字面 "\text{连续提升}"。
_LEAK_RE = re.compile(r"\\([a-zA-Z]+)|[{}]")


def render_math(src: str, display: bool = False):
    """把一段 LaTeX 转成 MathML 字符串。

    返回 (mathml, unknown)：unknown 是未识别命令名列表（非致命，构建期打印）。
    出口再自检一次残留的 LaTeX 标记，把它们也并进 unknown——构建期就能看见，
    而不是等用户看到页面上一串 "\text{...}" 才发现。
    """
    unknown: list = []
    parser = Parser(src, display=display, unknown=unknown)
    mml = parser.parse()
    for m in _LEAK_RE.finditer(mml):
        tok = ("\\" + m.group(1)) if m.group(1) else m.group(0)
        if tok not in unknown:
            unknown.append(tok)
    return mml, unknown


def scan_source(text: str):
    """抽出 Markdown 里的公式，返回 [(kind, latex), …]，kind ∈ {inline, block}。"""
    found = []
    i, n = 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == "$$":
            end = text.find("$$", i + 2)
            if end < 0:
                break
            found.append(("block", text[i + 2:end].strip()))
            i = end + 2
            continue
        if text[i] == "$":
            end = text.find("$", i + 1)
            if end < 0:
                break
            body = text[i + 1:end].strip()
            if body and "$" not in body:
                found.append(("inline", body))
            i = end + 1
            continue
        i += 1
    return found


if __name__ == "__main__":  # 自检
    for src in (
        r"\text{logits} = h \, W_{lm},\quad W_{lm} \in \mathbb{R}^{d_{model} \times V}",
        r"\qquad\Longrightarrow\qquad p = \operatorname{softmax}(\text{logits})",
        r"\operatorname{softmax}(z)_i = \frac{e^{z_i}}{\sum_{j=1}^{V} e^{z_j}}",
    ):
        print(render_math(src, display=True))
