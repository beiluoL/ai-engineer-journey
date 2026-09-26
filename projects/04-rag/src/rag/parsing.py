"""文档解析：把 .txt / .md / .pdf / .docx 统一解析成 Document（对应 milestone 01）。

想清楚一件事：RAG 的第一步不是检索，是「把乱七八糟的文档变成干净文本」。
Garbage in, garbage out —— 解析丢一段、乱一栏、混进页眉，后面每一环都在放大这个错误，
而且你几乎查不出来（检索结果"差不多但不准"，很难联想到是三个月前某个 PDF 解析坏了）。

对应 Java 的：接口 + 多实现 + 注册表（SPI / 策略模式）。
新增一种格式 = 新增一个类 + 注册进 PARSER_CLASSES，老代码零改动。
"""

from __future__ import annotations

import glob
import hashlib
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path

from .errors import DependencyMissingError, IngestionError
from .models import (
    META_FORMAT,
    META_HEADINGS,
    META_PARSED_AT,
    META_SIZE_BYTES,
    META_SOURCE,
    Document,
)

# Markdown 标题行：level 与 title 都要留给 02 章当语义边界用
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# 代码围栏：MdParser 只记录区间，不改写正文（改写在 chunker 里才安全）
_FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


def _read_text_fallback(path: Path) -> str:
    """编码三层回退：utf-8 → gbk → latin-1。

    文本文件没有自我声明的编码，.txt 不代表 utf-8（Windows 记事本默认 gbk）。
    Java 17 的 Files.readString(path, Charset) 强制显式传参是同一个道理。
    宁可出一点噪音，也别让整个摄入流水线崩掉。
    """
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise IngestionError(f"无法解码文件（试过 utf-8/gbk/latin-1）: {path}")


def _clean_text(text: str) -> str:
    """统一出口的清洗：删掉 C0 控制字符（含 PDF 提取常见的 \\x00）。

    放在统一出口而不是各 parser 内 —— 入口多个、出口只有一个，这是防漏的关键。
    """
    kept = [ch for ch in text if ch in ("\n", "\t") or ord(ch) >= 32]
    return "".join(kept).strip()


def _make_doc(path: Path, text: str, extra: dict | None = None) -> Document:
    """所有 parser 的统一出口：算 doc_id、清控制字符、塞 metadata。"""
    clean = _clean_text(text)
    payload = {
        # source 是检索溯组的命根子：没有它，Citation 只能打印 "unknown"
        META_SOURCE: str(path),
        META_FORMAT: path.suffix.lower().lstrip(".") or "unknown",
        META_SIZE_BYTES: path.stat().st_size,
        META_PARSED_AT: time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    payload.update(extra or {})
    return Document(
        # 内容哈希做主键：同一个文件重复摄入 → 同一个 doc_id → 天然幂等（01 §3.4）
        doc_id=hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16],
        source=str(path),
        text=clean,
        metadata=payload,
    )


class BaseParser(ABC):
    """格式适配器抽象基类。

    落地约定：parse() 返回 list[Document]（而不是 01 章设计稿里的单个 Document），
    因为 PDF 按页解析时一页就是一份独立的 Document，页面号进 metadata 供溯源。
    """

    supported_extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, path: Path) -> list[Document]:
        """读一个文件，返回 1~N 份 Document。"""

    @classmethod
    def supports(cls, path: Path | str) -> bool:
        return Path(path).suffix.lower() in cls.supported_extensions

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"{type(self).__name__}({self.supported_extensions})"


class TxtParser(BaseParser):
    supported_extensions = (".txt",)

    def parse(self, path: Path) -> list[Document]:
        return [_make_doc(path, _read_text_fallback(path))]


class MdParser(BaseParser):
    """Markdown：纯文本超集，但有两件必须做对的预处理（01 §3.2 注释）。

    1) 标题层级是天然语义边界 —— 记到 metadata["headings"]，02 章切分时按章节归属；
    2) 代码围栏内的文本不该被按句号切开 —— 记到 metadata["code_ranges"]（字符区间），
       02 章的切分器据此把代码块当成不可再分的原子单元。
    """

    supported_extensions = (".md", ".markdown")

    def parse(self, path: Path) -> list[Document]:
        raw = _read_text_fallback(path)
        headings: list[dict] = []
        for lineno, line in enumerate(raw.splitlines(), start=1):
            m = _HEADING_RE.match(line)
            if m:
                headings.append({
                    "level": len(m.group(1)),
                    "title": m.group(2).strip(),
                    "line": lineno,
                })
        metadata = {META_HEADINGS: headings,
                    "code_ranges": self._code_ranges(raw)}
        return [_make_doc(path, raw, metadata)]

    @staticmethod
    def _code_ranges(text: str) -> list[tuple[int, int]]:
        return [(m.start(), m.end()) for m in _FENCE_RE.finditer(text)]


class PdfParser(BaseParser):
    """PDF：pypdf 是**可选依赖**，没装时抛 DependencyMissingError（带 pip 提示）。"""

    supported_extensions = (".pdf",)

    def parse(self, path: Path) -> list[Document]:
        try:
            from pypdf import PdfReader  # 延迟 import：没装也要能 import 本模块
        except ImportError as e:
            raise DependencyMissingError(
                "pypdf", hint="解析 PDF 需要它："
            ) from e
        try:
            reader = PdfReader(str(path))
        except Exception as e:
            raise IngestionError(f"PDF 解析失败: {path} -> {e}") from e
        docs: list[Document] = []
        for i, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            # 页码内联在正文里，切分时可以带着走，溯源时就能报出页码
            docs.append(_make_doc(path, f"[第 {i} 页]\n{page_text}",
                                  {"page_no": i, "page_count": len(reader.pages)}))
        return docs


class DocxParser(BaseParser):
    """docx：python-docx 是可选依赖。表格必须单独遍历，doc.paragraphs 不含表格内容。"""

    supported_extensions = (".docx",)

    def parse(self, path: Path) -> list[Document]:
        try:
            from docx import Document as DocxDocument  # 延迟 import
        except ImportError as e:
            raise DependencyMissingError(
                "python-docx", hint="解析 docx 需要它："
            ) from e
        try:
            doc = DocxDocument(str(path))
        except Exception as e:
            raise IngestionError(f"docx 解析失败: {path} -> {e}") from e
        lines = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:  # 不遍历表格，表格信息会全部丢失
            cells = [c.text.strip() for row in table.rows for c in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
        return [_make_doc(path, "\n\n".join(lines))]


# 注册表：新增格式 = 新增一个类 + 往这里加一行
PARSER_CLASSES: tuple[type[BaseParser], ...] = (MdParser, TxtParser, PdfParser, DocxParser)


def get_parser(path: Path | str) -> BaseParser:
    """按后缀选解析器。注册表代替 if-elif（01 §3.3）。"""
    p = Path(path)
    for cls in PARSER_CLASSES:
        if cls.supports(p):
            return cls()
    raise IngestionError(
        f"不支持的格式: {p.suffix!r}（支持 .md/.markdown/.txt/.pdf/.docx）: {p}"
    )


def parse_file(path: Path | str) -> list[Document]:
    """摄入入口：文件 → list[Document]（01 §3.3 的 ingest() 落地版）。"""
    p = Path(path)
    if not p.is_file():
        raise IngestionError(f"文件不存在: {p}")
    return get_parser(p).parse(p)


def supported_extensions() -> tuple[str, ...]:
    """注册表支持的全部后缀。目录递归要靠它过滤（11 章坑 3）。"""
    out: list[str] = []
    for cls in PARSER_CLASSES:
        for ext in cls.supported_extensions:
            if ext not in out:
                out.append(ext)
    return tuple(out)


def expand_paths(paths, skip_report: bool = False) -> list[Path]:
    """把「文件 / 目录 / 通配」都摊平成文件列表，供 --index 用。

    11 章的坑 3（真实跑才会炸）：目录递归**必须按白名单过滤后缀**。
    当我们把 Chroma 的落盘目录放在 data/ 下面时，`rglob("*")` 会把
    `data/chroma-real/<uuid>/data_level0.bin` 也当成待摄入文件，然后
        IngestionError: 不支持的格式: '.bin'
    —— 炸在「我自己刚写出来的目录」上。这类 bug 单测永远照不到，
    因为它要求「先落盘、再摄入」的执行顺序，而单元测试用的是空目录。
    """
    exts = supported_extensions()
    out: list[Path] = []
    for item in paths:
        p = Path(item)
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if not child.is_file():
                    continue
                if child.suffix.lower() in exts:
                    out.append(child)
                elif skip_report:
                    print(f"  [skip] {child}（不支持的后缀 {child.suffix!r}）")
        elif p.exists() or any(ch in str(p) for ch in "*?["):
            for hit in sorted(Path(x) for x in glob.glob(str(p))):
                if hit.suffix.lower() in exts or not skip_report:
                    out.append(hit)
        else:
            out.append(p)
    return out
