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

import re
from abc import ABC, abstractmethod

from .errors import RerankError
from .models import ScoredChunk

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


def create_reranker(provider: str = "noop", **kwargs) -> BaseReranker:
    """rerank 工厂：接入层按配置选择实现，pipeline 只依赖抽象。"""
    if provider in ("noop", "none", ""):
        return NoopReranker()
    if provider == "fake":
        return FakeReranker(**kwargs)
    if provider == "siliconflow":
        return SiliconFlowReranker(**kwargs)
    raise RerankError(f"未知 rerank provider: {provider!r}（可选 noop/fake/siliconflow）")
