"""向量存储（对应 milestone 04）。

三阶段路线（04 §2）：
    ① 纯 Python + NumPy 暴力余弦 → InMemoryVectorStore，先懂原理，几百条够用
    ② Chroma（本地持久化 + HNSW）→ ChromaVectorStore，个人知识库首选
    ③ Milvus（生产级，十亿级）→ 本章提一句，不落地

关键语义约定：
    - `search` 返回 [(Chunk, score), ...]，降序；分数只用于排序，不用于解读（06 §4 纪律 2）。
    - `filter` 的语义 = **先过滤后搜**（04 §3.3）：先把候选集缩到目标文档，
      在子集内取 top-k，而不是全库 top-50 再筛（筛完可能一条不剩）。
    - `add` 用「主键 = chunk_id」的 upsert，重复 ingest 天然幂等（09 章坑 2）。
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from .errors import DependencyMissingError, EmbeddingError
from .models import Chunk
from .similarity import cosine_similarity_matrix, cosine_similarity

MODEL_KEY = "_model"
MODEL_SIDECAR = "_model"      # 落盘的模型名文件，刻意不带后缀


class BaseVectorStore(ABC):
    """向量存储抽象（04 §3.1）：存 (Chunk, vector)，查 top-k。"""

    @abstractmethod
    def add(self, chunks: list[Chunk], vectors: list[list[float]],
            model: str = "") -> None:
        """入库。model 记进元数据，供查询时校验（03 章坑 1 / 09 章坑 1 的防线）。"""

    @abstractmethod
    def search(self, query_vector: list[float], top_k: int = 5,
               filter: dict | None = None) -> list[tuple[Chunk, float]]:
        """返回 [(chunk, score), ...]，按相似度降序。"""

    @abstractmethod
    def count(self) -> int:
        """当前条目数。"""

    @abstractmethod
    def clear(self) -> None:
        """清空。"""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """按 chunk_id 删除若干条。"""

    @abstractmethod
    def delete_document(self, doc_id: str) -> None:
        """删除一个文档的所有块及其向量（04 坑 4：四处一起删）。"""

    def check_model(self, model: str) -> None:
        """查询前校验模型一致性：不同模型的向量空间互不相通（03 坑 1）。"""
        if model and self.model_name and model != self.model_name:
            raise EmbeddingError(
                f"embedding 模型不一致：库里是 {self.model_name!r}，当前查询用 {model!r}。"
                f"不同模型的向量空间互不相通，必须全量重建索引。"
            )


class InMemoryVectorStore(BaseVectorStore):
    """阶段 ①：内存向量库。NumPy 可用时走 `m @ q` 一次矩阵乘算全部相似度；
    没有 NumPy 时退回纯 Python 循环，两条路径结果一致。

    不变量（04 坑 4，任何时刻必须成立）：
        count() == len(_order) == len(_chunks) == len(_vectors)
    """

    def __init__(self) -> None:
        self.model_name: str = ""
        self._chunks: dict[str, Chunk] = {}
        self._vectors: dict[str, list[float]] = {}
        self._meta: dict[str, dict] = {}
        self._order: list[str] = []

    # ---- 写入 ----

    def add(self, chunks: list[Chunk], vectors: list[list[float]],
            model: str = "") -> None:
        if len(chunks) != len(vectors):
            raise EmbeddingError(
                f"chunks({len(chunks)}) 与 vectors({len(vectors)}) 数量不一致")
        for chunk, vec in zip(chunks, vectors):
            cid = chunk.chunk_id
            if cid in self._chunks:          # upsert：同 chunk_id 覆盖（幂等）
                self._order.remove(cid)
            elif model and self.model_name and model != self.model_name:
                # 往一个已用旧模型的库里混存新模型向量 = 埋雷（03 坑 1 / 04 坑 3）
                self.check_model(model)
            self._chunks[cid] = chunk
            self._vectors[cid] = list(vec)
            meta = dict(chunk.metadata)
            meta[MODEL_KEY] = model or self.model_name
            self._meta[cid] = meta
            self._order.append(cid)
        if model:
            self.model_name = model

    def delete(self, ids: list[str]) -> None:
        for cid in ids:
            self._chunks.pop(cid, None)
            self._vectors.pop(cid, None)
            self._meta.pop(cid, None)
            if cid in self._order:
                self._order.remove(cid)      # 四处一起删，避免"幽灵 chunk"

    def delete_document(self, doc_id: str) -> None:
        self.delete([cid for cid, c in self._chunks.items() if c.doc_id == doc_id])

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()
        self._meta.clear()
        self._order.clear()
        self.model_name = ""

    # ---- 查询 ----

    def vector_of(self, chunk_id: str) -> list[float]:
        """取回某块的向量，供 MMR 计算多样性（05 §3.4）。"""
        if chunk_id not in self._vectors:
            raise EmbeddingError(f"向量不存在: {chunk_id}")
        return self._vectors[chunk_id]

    def search(self, query_vector: list[float], top_k: int = 5,
               filter: dict | None = None) -> list[tuple[Chunk, float]]:
        if not self._order:
            return []
        ids = [cid for cid in self._order
               if _match(self._meta.get(cid, {}), filter)]   # 先过滤 → 再搜
        if not ids:
            return []
        matrix = [self._vectors[cid] for cid in ids]
        scores = cosine_similarity_matrix(matrix, query_vector)
        order = sorted(range(len(ids)), key=lambda i: -scores[i])
        out: list[tuple[Chunk, float]] = []
        for i in order:
            out.append((self._chunks[ids[i]], float(scores[i])))
            if len(out) >= top_k:
                break
        return out

    def count(self) -> int:
        return len(self._order)

    def __len__(self) -> int:
        return self.count()

    def check_invariant(self) -> None:
        """开发期自检：删文档时漏删任何一处，这里立刻炸（04 坑 4）。"""
        assert self.count() == len(self._chunks) == len(self._vectors) == len(self._meta)
        assert set(self._order) == set(self._chunks)


class ChromaVectorStore(BaseVectorStore):
    """阶段 ②：Chroma（本地持久化 + HNSW）。chromadb 是可选依赖，延迟 import。"""

    def __init__(self, persist_directory: str = "./data/chroma",
                 collection_name: str = "rag_chunks"):
        try:
            import chromadb  # 延迟 import：没装也要能 import 本模块
        except ImportError as e:
            raise DependencyMissingError(
                "chromadb", hint="本地持久化向量库需要它："
            ) from e
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(path=persist_directory)
        # collection 名必须 3~63 字符、只用字母数字和 -/_（04 坑 1），固定英文 snake_case
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        # 11 章坑 4：模型名必须**随库一起持久化**。
        # 上一版把 model_name 只放在实例属性上，进程一重启就变成空字符串，
        # check_model() 这道护栏当场失效 —— 用 bge-m3 建的库，
        # 重启后用 text-embedding-v3 检索也不会报警，两个空间直接混着用。
        #
        # 为什么不用 collection.modify(metadata=...)：Chroma 把 metadata 里的
        # hnsw:space 当成「距离函数」，一修改就报
        #     ValueError: Changing the distance function of a collection ...
        # 而 embedding 模型名是我们应用层的知识，不是 Chroma 的 ——
        # 所以老老实实写一个小 sidecar 文件。文件名故意不带后缀，
        # 免得被 expand_paths 当成待摄入的 .txt 文档。
        self.model_name = self._load_model()

    def add(self, chunks: list[Chunk], vectors: list[list[float]],
            model: str = "") -> None:
        # upsert 而非 add：重复入库变成覆盖，呼应 01 章的内容哈希幂等设计
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=[[float(x) for x in v] for v in vectors],
            documents=[c.text for c in chunks],
            metadatas=[self._meta_of(c, model) for c in chunks],
        )
        if model and model != self.model_name:
            self.model_name = model
            self._save_model(model)

    # ---- 模型名的持久化（11 章坑 4）----

    def _model_file(self) -> Path:
        return Path(self.persist_directory) / MODEL_SIDECAR

    def _load_model(self) -> str:
        p = self._model_file()
        return p.read_text(encoding="utf-8").strip() if p.is_file() else ""

    def _save_model(self, model: str) -> None:
        p = self._model_file()
        if model:
            p.write_text(model, encoding="utf-8")
        elif p.exists():
            p.unlink()

    @staticmethod
    def _meta_of(chunk: Chunk, model: str) -> dict:
        """Chunk.metadata → Chroma 能吃的 metadata 字典。

        这是「接真实服务」第一次真跑才炸出来的坑（11 章记录过现场）：
        MdParser 把 Markdown 的 headings 存成 **list**，而 Chroma 的 metadata
        只接受 str / int / float / bool，list 会直接抛
            ValueError: Expected metadata list value for key 'headings' to be non-empty in upsert
        另外 metadata 里可能混入 None（手工构造的 Document 常见），Chroma 也不收。
        所以入库前统一做一次「降维 + 去空」，而不是等线上炸了再查。
        """
        out = {"doc_id": chunk.doc_id, "index": chunk.index, MODEL_KEY: model}
        for k, v in chunk.metadata.items():
            flat = _to_scalar(v)
            if flat is not None:
                out[k] = flat
        return out

    def search(self, query_vector: list[float], top_k: int = 5,
               filter: dict | None = None) -> list[tuple[Chunk, float]]:
        kwargs: dict = {
            "query_embeddings": [[float(x) for x in query_vector]],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if filter:
            kwargs["where"] = filter          # Chroma 的 where 也是"先过滤后搜"
        res = self._collection.query(**kwargs)
        out: list[tuple[Chunk, float]] = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0],
                                        res["metadatas"][0], res["distances"][0]):
            chunk = Chunk(chunk_id=cid, doc_id=meta.get("doc_id", ""),
                          text=doc, index=int(meta.get("index", 0)), metadata=meta)
            # Chroma 返回的是**距离**（越小越像），换算回相似度，和内存库语义对齐
            out.append((chunk, similarity_from_distance(float(dist))))
        return out

    def count(self) -> int:
        return self._collection.count()

    def clear(self) -> None:
        name = self._collection.name
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"})
        self.model_name = ""
        self._save_model("")

    def delete(self, ids: list[str]) -> None:
        self._collection.delete(ids=ids)

    def delete_document(self, doc_id: str) -> None:
        self._collection.delete(where={"doc_id": doc_id})


def similarity_from_distance(distance: float) -> float:
    """Chroma 的距离 → 相似度（04 §3.4：score = 1 - distance）。"""
    return 1.0 - float(distance)


def _to_scalar(value: object) -> str | int | float | bool | None:
    """任意 Python 值 → Chroma metadata 允许的标量；没法转就返回 None（表示丢弃）。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        joined = ";".join(str(x) for x in value)   # headings 这类列表 → 字符串
        return joined or None
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def _match(meta: dict, filter: dict | None) -> bool:
    """metadata 过滤。字段名拼错时这里不会报错，只会匹配不上 —— 所以过滤条件
    尽量走常量（models.py 里的 META_*），并在接数据时逐步验证（05 坑 2）。"""
    if not filter:
        return True
    return all(meta.get(k) == v for k, v in filter.items())


__all__ = [
    "BaseVectorStore", "InMemoryVectorStore", "ChromaVectorStore",
    "MODEL_KEY", "similarity_from_distance", "cosine_similarity",
]
