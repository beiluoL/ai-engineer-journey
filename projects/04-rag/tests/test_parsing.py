"""parsing.py：解析层。重点验证「注册表 + 内容哈希 id + 扩展名支持判断」。"""

from __future__ import annotations

import pytest

from rag.errors import DependencyMissingError, IngestionError
from rag.models import META_CODE_RANGES, META_HEADINGS
from rag.parsing import (DocxParser, MdParser, PdfParser, TxtParser, PARSER_CLASSES,
                         expand_paths, get_parser, parse_file)


def test_supports_按后缀判断且忽略大小写():
    assert TxtParser.supports("a.TXT") and not TxtParser.supports("a.md")
    assert MdParser.supports("a.markdown") and not MdParser.supports("a.txt")
    assert PdfParser.supports("a.pdf") and DocxParser.supports("a.docx")


def test_parse_txt_文件_正文与元数据都对齐_dir(corpus_dir):
    docs = parse_file(corpus_dir / "python-gil.txt")
    assert len(docs) == 1
    doc = docs[0]
    assert doc.text.startswith("GIL 是什么")
    assert doc.metadata["source"].endswith("python-gil.txt")
    assert doc.metadata["format"] == "txt"


def test_parse_md_文件_抽出标题与代码围栏(corpus_dir):
    meta = parse_file(corpus_dir / "python-generators.md")[0].metadata
    titles = [h["title"] for h in meta[META_HEADINGS]]
    assert "生成器是什么" in titles
    assert meta[META_CODE_RANGES]              # 代码围栏要留给切分层，不能被拆散


def test_同内容重复解析_doc_id不变(corpus_dir):
    a = parse_file(corpus_dir / "python-generators.md")[0]
    b = parse_file(corpus_dir / "python-generators.md")[0]
    assert a.doc_id == b.doc_id                # 内容哈希 → 幂等的前提


def test_get_parser_不支持的格式明确报错(workdir):
    path = workdir / "a.doc"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(IngestionError):
        get_parser(path)


def test_缺可选依赖时报DependencyMissing而不是崩溃(workdir):
    # 本机没装 python-docx，正好验证「可选依赖 = 惰性导入 + 明确报错」
    path = workdir / "a.docx"
    path.write_bytes(b"PK\x03\x04")
    with pytest.raises(DependencyMissingError):
        parse_file(path)


def test_parse_file_文件不存在报错(workdir):
    with pytest.raises(IngestionError):
        parse_file(workdir / "missing.md")


def test_registry_里四个解析器都在():
    names = {cls.__name__ for cls in PARSER_CLASSES}
    assert names == {"MdParser", "TxtParser", "PdfParser", "DocxParser"}


def test_expand_paths_支持目录_文件与通配符(corpus_dir, workdir):
    sub = workdir / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("# b", encoding="utf-8")

    names = {p.name for p in expand_paths([str(corpus_dir)])}
    assert names == {"python-generators.md", "python-gil.txt", "b.md"}
    globbed = [p.name for p in expand_paths([str(workdir / "sub" / "*.md")])]
    assert globbed == ["b.md"]
    # 不存在的路径原样返回（交给下游报错），不静默吞掉
    assert expand_paths([str(workdir / "nope.md")]) == [workdir / "nope.md"]
