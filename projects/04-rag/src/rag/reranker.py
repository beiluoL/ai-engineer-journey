"""重排序（对应 milestone 07）。

两阶段检索架构（07 §2）：
    用户 query
      ↓ bi-encoder 粗召回：快（毫秒级），从全库捞 20 条（宁多勿漏）
      ↓ cross-encoder 精排：慢（几百毫秒），只对这 20 条逐对打分
      ↓ 取 top_n（如 5）交给 08 章拼 context

bi-encoder（03 章的 embedding）把 query 和 doc 各自独立编码，所以能离线预计算 ——
这就是向量库毫秒响应的原因，代价是它判断不了「这段文档对**这个问题**有没有用」。
cross-encoder 把两者拼成一段一起送进模型，能算细粒度对应，但每对都要一次前向推理，
无法预计算 —— 所以只能精排少量候选，绝不能拿来全库检索（07 坑 4）。

一个必须记住的纪律（07 坑 1）：rerank 分数与余弦分数**语义不同**，不可混用排序。
rerank 之后以 rerank 分数为准全盘重排，向量分数只留给日志/调试。
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

from .errors import RerankError
from .models import ScoredChunk

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[一-鿿]|[A-Za-z_][A-Za-z0-9_]*|\d+")


class BaseReranker(ABC):
    """rerank 契约：输入 query + 候选 chunks，输出按相关性降序的前 top_n 条。

    实现纪律（07 §3.2）：
        ① 必须截断到 top_n（双保险：min(top_n, len) + 返回前再截一次）；
        ② 分数覆写进 ScoredChunk.score；
        ③ 不修改传入列表的顺序，返回新列表。
    """

    model_name = ""

    @abstractmethod
    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int = 5
               ) -> list[ScoredChunk]:
        ...


class NoopReranker(BaseReranker):
    """直通实现：原样返回前 top_n 条。

    测试和降级路径专用（07 §3.2 的 NoOp 模式）：让 pipeline 代码不感知 rerank
    有没有真的发生 —— 只依赖 BaseReranker 抽象，换实现不改一行 pipeline 代码。
    """

    model_name = "noop"

    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int = 5
               ) -> list[ScoredChunk]:
        return chunks[:top_n]


class FakeReranker(BaseReranker):
    """离线可用的「关键词覆盖度」精排（生产环境换成 SiliconFlowReranker）。

    它模拟的是 cross-encoder 的**行为形态**：对 (query, doc) 这一对单独打分、
    能改变顺序（而不只是截断）、分数与余弦分数语义不同。
    具体打分用「query 命中的字符/词占 query 的比例」，确定性、不联网。
    """

    model_name = "fake-keyword"

    def __init__(self, boost_title: bool = True):
        self.boost_title = boost_title

    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int = 5
               ) -> list[ScoredChunk]:
        if not chunks:
            return []
        top_n = min(top_n, len(chunks))
        q_tokens = set(_TOKEN_RE.findall(query.lower()))
        scored: list[ScoredChunk] = []
        for sc in chunks:
            text = sc.chunk.text.lower()
            hits = sum(1 for t in q_tokens if t in text)
            ratio = hits / len(q_tokens) if q_tokens else 0.0
            # 长度惩罚：越长越像"沾边不相关"（和 cross-encoder 的直觉一致）
            length_penalty = min(len(sc.chunk.text) / 600, 1.0) * 0.15
            raw = ratio - length_penalty
            if self.boost_title and sc.chunk.metadata.get("format") == "md":
                raw += 0.02      # 标题类 markdown 略加权，模拟标题命中
            scored.append(ScoredChunk(chunk=sc.chunk, score=round(raw, 4)))
        scored.sort(key=lambda s: -s.score)
        return scored[:top_n]


class SiliconFlowReranker(BaseReranker):
    """真实 API 精排：bge-reranker-v2-m3 走 SiliconFlow rerank 接口。

    只在接入层按配置注入；测试与离线 demo 用 NoopReranker / FakeReranker。
    发送前主动截断到 max_doc_chars（07 坑 3：超长 chunk 被服务端静默剪掉，
    剪掉的恰好可能是答案，表现是"长文档永远排不进 top_n"）。
    """

    model_name = "BAAI/bge-reranker-v2-m3"

    def __init__(self, api_key: str, model: str = model_name,
                 max_doc_chars: int = 4000):
        if not api_key:
            raise RerankError("api_key 为空，无法调用 rerank 接口")
        self.api_key = api_key
        self.model = model
        self.max_doc_chars = max_doc_chars

    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int = 5
               ) -> list[ScoredChunk]:
        import httpx

        if not chunks:
            return []
        top_n = min(top_n, len(chunks))
        try:
            resp = httpx.post(
                "https://api.siliconflow.cn/v1/rerank",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "query": query,
                    "documents": [c.text[: self.max_doc_chars] for c in chunks],
                    "top_n": top_n,
                },
                timeout=30,
            )
        except Exception as e:  # noqa: BLE001 - 转成自己的异常层级
            raise RerankError(f"rerank 请求失败: {e}") from e
        if resp.status_code in (401, 403):
            raise RerankError(f"rerank 认证失败（{resp.status_code}）")
        resp.raise_for_status()
        try:
            results = resp.json()["results"]
        except Exception as e:  # noqa: BLE001
            raise RerankError(f"rerank 响应结构异常: {resp.text[:200]}") from e
        out: list[ScoredChunk] = []
        for r in results:                       # API 已按分数降序返回
            chunk = chunks[r["index"]]
            out.append(ScoredChunk(chunk=chunk, score=float(r["relevance_score"])))
        return out[:top_n]                      # 双保险：即使 API 忽略 top_n 也截断


class LLMReranker(BaseReranker):
    """用真实 LLM 做 listwise 精排（真实 cross-encoder 不可用时的落地方案）。

    为什么会有这个实现：cross-encoder（bge-reranker-v2-m3）本该是首选，但它依赖
    SiliconFlow / 百炼的 rerank 接口 —— 本机既没有 SILICONFLOW_API_KEY，百炼的
    gte-rerank 也返回 403 AccessDenied（账号未开通）。与其在文档里假装接了真实
    reranker，不如用**真能调通**的 DeepSeek 做同样的事：把 (query, 候选) 一起
    送进模型，让它输出编号序列 —— 这正是 cross-encoder「逐对一起看」的思想。

    实测（deepseek-chat，5 条候选）：0.82s、157 token，排序准确。

    两条必须知道的取舍：
        ① **分数只表达顺序，不表达置信度**。LLM 不给分，这里按名次线性递减
           造一个分数，它只能用于排序，不能和余弦分数比大小、也不能设阈值；
        ② **成本是 O(候选数)**。所以默认只看前 max_candidates 条，且每条截断
           max_doc_chars —— 这正是 07 章「粗召回宁多勿漏、精排只做少量」的边界。
    """

    model_name = "llm-listwise"

    def __init__(self, llm, max_candidates: int = 12,
                 max_doc_chars: int = 300, temperature: float = 0.0):
        self._llm = llm
        self.max_candidates = max_candidates
        self.max_doc_chars = max_doc_chars
        self.temperature = temperature
        # 降级是可观测信号：它频次一高就说明 prompt 或模型选得不对，
        # 而不是「偶发抖动」。不记下来就只能靠猜。
        self.degraded = 0
        self.degraded_queries: list[str] = []

    def rerank(self, query: str, chunks: list[ScoredChunk], top_n: int = 5
               ) -> list[ScoredChunk]:
        if not chunks:
            return []
        top_n = min(top_n, len(chunks))
        # 只让模型看前 max_candidates 条；后面的按原顺序垫底，不会被丢掉。
        head = chunks[: self.max_candidates]
        tail = chunks[self.max_candidates:]

        prompt = self._build_prompt(query, head)
        try:
            raw = self._llm.chat([{"role": "user", "content": prompt}])
        except Exception as e:  # noqa: BLE001 - 服务故障要显式报错，交给接入层降级
            raise RerankError(f"LLM rerank 调用失败: {e}") from e

        order = _parse_ranking(raw, len(head))
        if order is None:
            # 模型没按格式答：这是「模型行为」不是「服务故障」，降级为原顺序，
            # 顺序是次优的但仍然可用 —— 不该让一次格式抖动就把整条问答链路打断。
            self.degraded += 1
            self.degraded_queries.append(query)
            logger.warning("LLM rerank 输出无法解析为编号序列，降级为原顺序: %r",
                           raw[:80])
            order = list(range(len(head)))

        ranked = [head[i] for i in order] + [head[i] for i in range(len(head))
                                             if i not in order] + tail
        out: list[ScoredChunk] = []
        for rank, sc in enumerate(ranked):
            # 名次 → 分数：只保证单调递减，数值本身没有概率含义
            out.append(ScoredChunk(chunk=sc.chunk, score=round(1.0 - rank * 0.05, 4)))
        return out[:top_n]

    def _build_prompt(self, query: str, chunks: list[ScoredChunk]) -> str:
        lines = [f"[{i}] {c.chunk.text[: self.max_doc_chars]}"
                 for i, c in enumerate(chunks)]
        return (
            "下面是若干候选片段，判断它们能回答该问题的程度，从高到低排序。\n"
            f"只输出前 {min(len(chunks), 10)} 个编号，用逗号分隔，不要输出任何解释。\n\n"
            f"问题：{query}\n\n候选：\n" + "\n".join(lines) + "\n\n编号序列："
        )


_RANK_NUM_RE = re.compile(r"\d+")


def _parse_ranking(text: str, n: int) -> list[int] | None:
    """把「0,2,4」这类输出解析成去重且合法的编号列表；解析不出返回 None。"""
    if not text:
        return None
    order: list[int] = []
    for tok in _RANK_NUM_RE.findall(text):
        idx = int(tok)
        if 0 <= idx < n and idx not in order:
            order.append(idx)
    return order or None


def create_reranker(provider: str = "noop", **kwargs) -> BaseReranker:
    """rerank 工厂：接入层按配置选择实现，pipeline 只依赖抽象。"""
    if provider in ("noop", "none", ""):
        return NoopReranker()
    if provider == "fake":
        return FakeReranker(**kwargs)
    if provider == "siliconflow":
        return SiliconFlowReranker(**kwargs)
    if provider == "llm":
        return LLMReranker(**kwargs)
    raise RerankError(
        f"未知 rerank provider: {provider!r}（可选 noop/fake/siliconflow/llm）")
