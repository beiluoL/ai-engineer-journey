"""RAG 的通用数据模型：Document / Chunk / ScoredChunk。

对应 milestone：
    - 01 §3.1  Document（内容哈希做 doc_id）
    - 02 §3.1  Chunk（chunk_id = f"{doc_id}-{index}"，溯源链的关键）
    - 05 §5     ScoredChunk（检索结果 = 块 + 分数）

两条贯穿全模块的设计约定（01 章与 02 章已发布，不要改）：
    1. id 从内容派生 —— doc_id = sha256(正文)[:16]，chunk_id = doc_id + "-" + index。
       重复摄入同一个文件会产生同一个 id，天然幂等（ upsert 覆盖，不会翻倍）。
    2. 溯源信息跟着块走 —— Chunk.metadata 里合并了 Document.metadata（source/format/…）
       以及本块在原文中的位置（start_char / end_char / start_line / end_line），
       组装阶段（08 章）就是靠它生成 [1] (source: xxx.md#L12-40) 这类引用。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 元数据字段名的集中定义：避免各处裸字符串拼错（05 章坑 2 的防线之一）
META_SOURCE = "source"
META_FORMAT = "format"
META_SIZE_BYTES = "size_bytes"
META_PARSED_AT = "parsed_at"
META_HEADINGS = "headings"
META_CODE_RANGES = "code_ranges"
META_START_CHAR = "start_char"
META_END_CHAR = "end_char"
META_START_LINE = "start_line"
META_END_LINE = "end_line"


@dataclass
class Document:
    """一份文档 = 干净正文 + 来源 + 元数据。

    对应 milestone 01 §3.1 的 dataclass，字段顺序照抄文档，新增字段都带默认值。
    metadata 约定存：format / size_bytes / parsed_at（01 章），
    Markdown 额外存 headings 与 code_ranges（供 02 章切分使用）。
    """

    doc_id: str
    source: str
    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def char_count(self) -> int:
        return len(self.text)

    @property
    def line_count(self) -> int:
        return self.text.count("\n") + 1


@dataclass
class Chunk:
    """一个切分块。切分的最小单位，也是检索的最小单位（02 章）。"""

    chunk_id: str
    doc_id: str
    text: str
    index: int
    metadata: dict = field(default_factory=dict)

    @property
    def source(self) -> str:
        """命中后展示出处用（从 metadata 里取，取不到给个占位）。"""
        return self.metadata.get(META_SOURCE, "unknown")

    @property
    def start_char(self) -> int:
        return int(self.metadata.get(META_START_CHAR, 0))


@dataclass
class ScoredChunk:
    """检索产物：块 + 相似度分数（05 章的返回类型）。

    分数来自哪一段由调用方决定：
        - 向量检索阶段 = 余弦相似度；
        - rerank 之后 = 精排模型的相关性分数（07 章：两者语义不同，不可混用排序）。
    """

    chunk: Chunk
    score: float

    @property
    def chunk_id(self) -> str:
        """05 章设计稿里直接用 h.chunk_id 取 id，这里补一个便捷属性。"""
        return self.chunk.chunk_id

    @property
    def source(self) -> str:
        return self.chunk.source
