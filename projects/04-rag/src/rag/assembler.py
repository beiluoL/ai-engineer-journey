"""上下文组装（对应 milestone 08）。

检索层产出的是「原材料」，组装层产出的是「成品 prompt」。为什么要分两层：

    不溯源 → 模型说"RAG 的全称是检索增强生成"，这句话出自哪份文档？用户只能全信或全不信，
             幻觉就在这个「无法验证」的缝隙里长出来；
    不控预算 → top_k 是按条数截断的，不是按 token，5 条 800 token 的块加 system 就撞窗；
    不管顺序 → 模型对超长上下文的注意力呈 U 形，中间容易被忽略（lost in the middle）。

三条规则缺一不可（08 §3.1 的 system prompt）：
    1) 只依据【参考资料】回答；2) 引用用编号标注；3) 资料不足就明确说「不知道」。
没有第 3 条，模型在资料不相关时依然会用自身知识"热心"作答 —— 那是幻觉高发区。

一个关键细节（08 §3.3）：`[n]` 编号是本次请求临时分配的，同一份文档两次提问编号不同。
所以 Citation 同时存稳定键（source + chunk_index + start_char）和临时编号 no ——
持久定位靠稳定键，回答里的 `[n]` 靠 no 对上（就像 REST 响应同时带业务键和展示序号）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .chunker import estimate_tokens
from .models import META_END_LINE, META_START_CHAR, META_START_LINE, Chunk, ScoredChunk

# 每个 RAG 问答请求都带的 system 规则（08 §3.1）
RAG_SYSTEM_RULES = (
    "你是知识库问答助手。请严格遵守：\n"
    "1. 只依据下面的【参考资料】回答用户问题。\n"
    "2. 引用资料时用编号标注，如 [1]、[2]。\n"
    "3. 如果参考资料不足以回答问题，直接说「知识库中没有相关资料」，"
    "不要使用你自己的知识，不要编造。\n"
)


@dataclass(frozen=True)
class Citation:
    """一条引用：临时编号（no）+ 稳定定位键（source / chunk_index / start_char）。

    行号是展示层格式，由组装阶段元数据的 start_line/end_line 换算而来，
    目标是用户拿着引用能回到原文档的精确位置。
    """

    no: int
    source: str
    chunk_index: int
    start_char: int
    start_line: int = 0
    end_line: int = 0

    def anchor(self) -> str:
        """展示层锚点，形如 data/python-generators.md#L12-40。"""
        return f"{self.source}#L{self.start_line}-{self.end_line}"


@dataclass(frozen=True)
class AssembledContext:
    """组装产物：给模型的资料正文 + 用了哪些块 + 引用列表 + token 占用。"""

    context_text: str
    used_chunks: list[ScoredChunk] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    context_tokens: int = 0

    @property
    def n_used(self) -> int:
        return len(self.used_chunks)


class ContextAssembler:
    """把检索结果组装成可溯源、预算可控的 prompt 资料。"""

    def __init__(self, min_score: float = 0.2) -> None:
        # 分数低于阈值的资料视为噪声（08 §4：装进去只会稀释注意力）
        self._min_score = min_score

    def build(
        self,
        query: str,
        scored_chunks: list[ScoredChunk],
        budget: int,
    ) -> AssembledContext:
        """在 budget _token 内，按分数从高到低装资料；装不下就停。

        budget 由调用方传入（09 章的 Settings）而不是自己算 —— 窗口多大、给输出
        留多少是配置层的事，组装层只负责「在给定空间内装最优的」。
        """
        if budget <= 0:
            return AssembledContext(context_text="", used_chunks=[], citations=[],
                                    context_tokens=0)

        used: list[ScoredChunk] = []
        citations: list[Citation] = []
        blocks: list[str] = []
        seen: set[str] = set()            # 按内容去重：overlap 造成的近似重复（08 坑 1）
        total = 0

        for sc in sorted(scored_chunks, key=lambda s: s.score, reverse=True):
            if sc.score < self._min_score:
                break                     # 分数是有序的，装不下就停，不跳过继续装
            key = sc.chunk.text.strip()
            if key in seen:
                continue
            seen.add(key)

            block = self._format_block(no=len(used) + 1, chunk=sc.chunk)
            cost = estimate_tokens(block) + 1
            if total + cost > budget:     # 分数截断：宁可少放一条完整的，不要四条残缺的
                break

            used.append(sc)
            # 编号分配与 citations 生成必须在同一次遍历里完成（08 坑 4）：
            # 排序 / 去重 / 预算截断任何一步改变顺序，两者天然保持一致
            citations.append(self._to_citation(no=len(used), chunk=sc.chunk))
            blocks.append(block)
            total += cost

        return AssembledContext(
            context_text="\n\n".join(blocks),
            used_chunks=used,
            citations=citations,
            context_tokens=total,
        )

    # 文档 05/09 的任务书里用的是 assemble 这个名字，两者是同一个方法
    assemble = build

    def _format_block(self, no: int, chunk: Chunk) -> str:
        """一条资料的格式：`[1] (source: xxx.md#L12-40)` + 正文。"""
        meta = chunk.metadata
        source = meta.get("source", "unknown")
        start_line = meta.get(META_START_LINE, 0)
        end_line = meta.get(META_END_LINE, 0)
        start_char = meta.get(META_START_CHAR, 0)
        end_char = start_char + len(chunk.text)
        anchor = f"L{start_line}-{end_line}" if end_line else f"char-{start_char}-{end_char}"
        return f"[{no}] (source: {source}#{anchor})\n{chunk.text}"

    @staticmethod
    def _to_citation(no: int, chunk: Chunk) -> Citation:
        meta = chunk.metadata
        return Citation(
            no=no,
            source=meta.get("source", "unknown"),
            chunk_index=chunk.index,
            start_char=meta.get(META_START_CHAR, 0),
            start_line=meta.get(META_START_LINE, 0),
            end_line=meta.get(META_END_LINE, 0),
        )
