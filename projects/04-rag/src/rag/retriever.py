"""检索门面（对应 milestone 05）。

一条 query 从用户输入到变成 chunk 列表，五步（05 §3.1）：
    ① 预处理：截断（query 长度受 embedding 模型输入上限约束）
    ② embed：query → 向量（必须与入库同一个模型！）
    ③ 向量库 top-k
    ④ metadata 过滤（先过滤后搜）
    ⑤ 返回 list[ScoredChunk]

为什么叫门面：上层（09 章的 pipeline）只需要 `retriever.retrieve(query, top_k=5)`，
策略全部带默认值 —— Java 里「@Service 聚合多个 DAO，对上层只暴露一个方法」。
为什么策略是参数不是子类：`mode` / `mmr` 用参数切换，避免 HybridMmrRetriever 类爆炸。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .embedding import run_sync
from .errors import ConfigurationError
from .models import ScoredChunk
from .similarity import cosine_similarity
from .store import BaseVectorStore

# 中文按字、英文按词的极简分词（避免引入 jieba）
_TOKEN_RE = re.compile(r"[一-鿿]|[A-Za-z_][A-Za-z0-9_]*|\d+")


def rrf_fuse(rankings: list[list[str]], k: int = 60) -> list[str]:
    """RRF 倒数排名融合（05 §3.3）：RRF_score(doc) = Σ 1/(k + rank_i)。

    只消费**排名**不消费分数 —— 两路分数量纲完全不同（余弦 0~1 vs BM25 3.7/15.2），
    直接加权求和等于拿米和斤做加法，关键词路会永远碾压向量路（05 坑 3）。
    k=60 是平滑常数，压低头部排名的影响，让融合更看重"两路都认"。
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda x: -x[1])]


class KeywordIndex:
    """极简 BM25 关键词索引（05 §3.3 的"关键词路"）。

    向量检索擅长语义，搞不定 `setTimeout`、`ECONNRESET` 这类精确符号（被 embedding
    泛化掉了）；BM25 正好相反。混合检索就是拿这两路互补。

    这里不需要分词器：中文按字索引、英文按词索引，对中文语料的召回已经够用。
    """

    K1 = 1.5
    B = 0.75

    def __init__(self) -> None:
        self._postings: dict[str, dict[str, int]] = {}   # 词 → {chunk_id: tf}
        self._lens: dict[str, int] = {}
        self._chunks: dict[str, object] = {}             # chunk_id → Chunk（回填结果用）
        self._avg_len = 0.0

    def index(self, chunks) -> None:
        for chunk in chunks:
            self.add(chunk)

    def add(self, chunk) -> None:
        tokens = self.tokenize(chunk.text)
        self._chunks[chunk.chunk_id] = chunk
        self._lens[chunk.chunk_id] = len(tokens)
        postings = self._postings
        for t in tokens:
            postings.setdefault(t, {})
            postings[t][chunk.chunk_id] = postings[t].get(chunk.chunk_id, 0) + 1
        total = sum(self._lens.values())
        self._avg_len = total / len(self._lens) if self._lens else 0.0

    def tokenize(self, text: str) -> list[str]:
        return [t.lower() for t in _TOKEN_RE.findall(text)]

    def search(self, query: str, top_k: int = 5, filter: dict | None = None,
               id_to_chunk: dict | None = None) -> list[tuple]:
        tokens = self.tokenize(query)
        n = len(self._lens)
        scores: dict[str, float] = {}
        for t in tokens:
            postings = self._postings.get(t)
            if not postings:
                continue
            idf = max(1.0, math.log(1 + (n - len(postings) + 0.5) / (len(postings) + 0.5)))
            for cid, tf in postings.items():
                norm = self._avg_len or 1.0
                denom = tf + self.K1 * (1 - self.B + self.B * self._lens[cid] / norm)
                scores[cid] = scores.get(cid, 0.0) + idf * self.K1 / denom
        # 先打分排序、再逐条按 filter 丢弃，最后才截断 top_k
        order = sorted(scores.items(), key=lambda x: -x[1])
        out: list[tuple] = []
        for cid, score in order:
            # id_to_chunk 由调用方带进来（= 向量路的已有结果，只补它没召回的），
            # 没带就用关键词索引自己存的 —— 绝不能因为映射缺失就静默返回空列表。
            chunk = (id_to_chunk if id_to_chunk is not None else self._chunks).get(cid)
            if chunk is None:
                continue
            if filter and not all(chunk.metadata.get(k) == v
                                  for k, v in filter.items()):
                continue
            out.append((chunk, float(score)))
            if len(out) >= top_k:
                break
        return out


@dataclass
class Retriever:
    """检索门面。Java 类比：一个 @Service 聚合了 EmbeddingDao 和 VectorStoreDao。"""

    embedding_client: object
    vector_store: BaseVectorStore
    rrf_k: int = 60
    mmr_lambda: float = 0.7            # 1.0 = 纯相关性；0.5~0.7 兼顾多样性
    use_keyword: bool = True           # hybrid 模式下的关键词路开关

    def __post_init__(self) -> None:
        self._keyword = KeywordIndex()

    # ---- 索引侧：把 chunk 也喂给关键词路 ----

    def index(self, chunks) -> None:
        """入库后调用一次，建关键词索引（hybrid 模式才需要）。"""
        self._keyword.index(chunks)

    # ---- 查询侧 ----

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filter: dict | None = None,
        mode: str = "vector",       # "vector" | "hybrid"
        mmr: bool = False,
        fetch_k: int = 20,          # 粗召回数量（mmr / rerank 场景取大值）
    ) -> list[ScoredChunk]:
        if not query or not query.strip():
            raise ConfigurationError("query 不能为空")

        query = self._truncate(query)                                    # ① 预处理
        query_vec = run_sync(self.embedding_client.embed_one(query))     # ② 单条嵌入
        self.vector_store.check_model(self.embedding_client.model_name)

        if mode == "vector":
            hits = [(c, s) for c, s in
                    self.vector_store.search(query_vec, top_k=fetch_k, filter=filter)]
        elif mode == "hybrid":
            hits = self._hybrid_search(query, query_vec, fetch_k, filter)
        else:
            raise ConfigurationError(f"未知 mode: {mode!r}（可选 vector / hybrid）")

        scored = [ScoredChunk(chunk=c, score=float(s)) for c, s in hits]
        if mmr and len(scored) > top_k:
            scored = self._mmr_select(query_vec, scored, top_k)
        return scored[:top_k]                                   # 粗召回 → 最终 top_k

    def _truncate(self, query: str, max_chars: int = 1024) -> str:
        """embedding 模型有输入上限，超长 query 静默截断会丢语义，这里显式处理（05 坑 1）。"""
        return query[:max_chars]

    def _hybrid_search(self, query: str, query_vec: list[float], fetch_k: int,
                       filter: dict | None) -> list[tuple]:
        vec_hits = self.vector_store.search(query_vec, top_k=fetch_k, filter=filter)
        if self.use_keyword:
            id_to_chunk = {c.chunk_id: c for c, _ in vec_hits}
            kw_hits = self._keyword.search(query, top_k=fetch_k, filter=filter,
                                           id_to_chunk=id_to_chunk)
        else:
            kw_hits = []
        # RRF 只认排名不认分数 → 两路安全融合
        fused_ids = rrf_fuse([[c.chunk_id for c, _ in vec_hits],
                              [c.chunk_id for c, _ in kw_hits]], k=self.rrf_k)
        by_id: dict[str, tuple] = {}
        for hit in vec_hits:                       # 有向量分就用向量分
            by_id[hit[0].chunk_id] = hit
        for hit in kw_hits:                        # 只有关键词路命中的，用关键词分
            by_id.setdefault(hit[0].chunk_id, hit)
        return [by_id[i] for i in fused_ids if i in by_id][:fetch_k]

    def _mmr_select(self, query_vec: list[float], candidates: list[ScoredChunk],
                    top_k: int) -> list[ScoredChunk]:
        """贪心 MMR（05 §3.4）：MMR = λ·sim(query) − (1−λ)·max_sim(已选)。

        λ=1 退化为普通 top-k；λ=0 只顾彼此最不相似；实践取 0.5~0.7。
        """
        selected: list[ScoredChunk] = []
        pool = list(candidates)
        while pool and len(selected) < top_k:
            best, best_score = None, float("-inf")
            for cand in pool:
                rel = cosine_similarity(query_vec, self.vector_store.vector_of(cand.chunk_id))
                max_div = 0.0
                if selected:
                    max_div = max(
                        cosine_similarity(
                            self.vector_store.vector_of(s.chunk_id),
                            self.vector_store.vector_of(cand.chunk_id))
                        for s in selected)
                score = self.mmr_lambda * rel - (1 - self.mmr_lambda) * max_div
                if score > best_score:
                    best, best_score = cand, score
            if best is None:
                break
            selected.append(best)
            pool.remove(best)
        return selected
