"""生成侧的最小契约（对应 milestone 09 §3.1「模型层」）。

RAG 的在线问答链路和 P03 的 chat 应用几乎一模一样：
    system + user → LLM → 回答
RAG 只多了两件事 —— 前置的检索阶段和一条离线索引链路。
所以生成侧不重新发明：真实接入层直接复用 P03 的 DeepSeek client；
这里只留下**离线契约**，让 `RAGService.ask()` 能在不联网、不花钱的前提下端到端跑通。

FakeLLMClient 的行为是确定性的：从【参考资料】里挑出和问题最相关的一两句，
带上 [n] 编号拼成答案。它不改变流水线结构，只替换掉"生成"这一步的实现。
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .errors import RAGError

_CONTEXT_BLOCK_RE = re.compile(r"(?m)^\[(\d+)\] \(source: ([^)]+)\)$")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s")
_CJK = r"[一-鿿]"


def _iter_blocks(system: str) -> list[tuple[int, str, str]]:
    r"""把【参考资料】切成 [(编号, 来源, 正文)]。

    为什么不用「一次正则吃掉整块」：块的正文里有换行，`.` 默认不匹配换行，
    写 ``^\[(\d+)\] \(source: ([^)]+)\)\n(.*)$`` 会**只截到块的第一行** ——
    正文的其余部分全丢，最后只能抽到标题行。这里改成先按块首标记切，
    再取该标记到下一个块首之间的内容。
    """
    marks = list(_CONTEXT_BLOCK_RE.finditer(system))
    blocks: list[tuple[int, str, str]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(system)
        body = system[m.end():end].lstrip("\n")
        blocks.append((int(m.group(1)), m.group(2), body))
    return blocks


class BaseLLMClient(ABC):
    """生成侧抽象。接真实模型时实现 chat() 即可，RAGService 一行不用改。"""

    model_name: str = ""

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """messages = [{"role": "system"|"user", "content": str}] → 回答文本。"""


class FakeLLMClient(BaseLLMClient):
    """离线替身：从 system 里的【参考资料】中抽取与 user 问题重叠最多的句子。

    它让 09 章的失败语义（检索为空直接拒答、citations 随答案一起产出）
    在没有 API Key 的情况下也能被完整测到。
    """

    model_name = "fake-llm"

    def __init__(self, max_sentences: int = 6, min_overlap: int = 3):
        self.max_sentences = max_sentences
        # 至少命中这么多个 query 词才肯作答，否则视作「资料与问题无关」→ 拒答。
        # 这一条对应 09 章的失败语义 2：宁可说「不知道」，也不要胡编。
        self.min_overlap = min_overlap

    def chat(self, messages: list[dict]) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        query_tokens = set(re.findall(_CJK, user)) | {
            w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", user)}

        picked: list[tuple[int, float, int, str, str]] = []
        for no, source, body in _iter_blocks(system):
            for sent in _split_sentences(body):
                if _HEADING_RE.match(sent):
                    continue          # 标题行不当答案（"## 为什么能省内存" 不是回答）
                toks = set(re.findall(_CJK, sent)) | {
                    w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sent)}
                covered = len(toks & query_tokens)
                if covered < self.min_overlap:
                    continue
                # 主排序看「覆盖了多少 query 词」，保证答案里带上关键概念，
                # 次排序看重叠比例，避免挑到最长的那段
                picked.append((covered, covered / max(len(toks), 1), int(no),
                               sent.strip(), source, toks))

        # 按「覆盖了多少 query 词」降序取前几句：候选句子已经按句切好，
        # 排序键是 (覆盖词数, 覆盖比例, 出处编号)，先保概念全，再保句子短。
        # 注意这里不做贪心集合覆盖 —— 先覆盖再覆盖别的词会让第一句（标题行）
        # 把所有词都「占」掉，后面真正带关键词的句子一个都选不进来。
        pool = sorted(picked, key=lambda x: (-x[0], -x[1], x[2]))
        chosen = [(p[2], p[3], p[4]) for p in pool[: self.max_sentences]]
        if not chosen:
            return "知识库中没有相关资料，无法回答这个问题。"
        lines = [f"[{no}] {sent}（来源: {source}）" for no, sent, source in chosen]
        return "根据知识库资料回答：" + "；".join(lines) + "。"


class RAGLLMError(RAGError):
    """生成侧调用失败（09 章失败语义 3：重试一次，仍失败要明确报错）。"""


def _split_sentences(text: str) -> list[str]:
    """按中英文句末标点切句，供 FakeLLMClient 抽取句子用。"""
    parts = re.split(r"(?<=[。！？!?])", text)
    return [p for p in (s.strip() for s in parts) if p]
