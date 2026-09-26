"""文本向量化（对应 milestone 03）。

核心直觉（03 §2）：
    哈希是「精确相等」的指纹，embedding 是「语义相似」的指纹。
    SHA-256：内容变一个比特，指纹完全不同（回答"这两段文本一模一样吗"）。
    Embedding：两段说得差不多的话，向量在空间里很接近（回答"意思接近吗"）。

为什么接口是**批量** `embed(texts: list[str])` 而不是单个？
    一句话向量化一次 HTTP 往返，1000 个块就是 1000 次请求 —— 限流、延迟全爆。
    批量一次往返处理几十上百条，这是 embedding 与 chat 最大的接口差异。

Java 类比：`EmbeddingClient` 接口 + `@Profile("prod")` 真实实现 /
`@Profile("test")` Fake 实现，上层只依赖接口（Python 里靠构造函数传入手工 DI）。
"""

from __future__ import annotations

import hashlib
import math
import os
from abc import ABC, abstractmethod

from .errors import EmbeddingError, EmbeddingRateLimitError
from .similarity import normalize


def run_sync(coro):
    """在同步入口（cli / demo / 测试）里跑异步调用。

    为什么还要保留 async 接口：真实 embedding 客户端是 I/O 密集的（03 §3.3 用 httpx 异步），
    但索引链路和问答链路对上层是同步的（09 章的 ingest/ask 都是同步方法），
    所以这里用 asyncio.run 收口 —— 一个进程内只跑一次事件循环，够用且不易出错。
    """
    import asyncio

    return asyncio.run(coro)

# SiliconFlow 托管的 bge 系列：中文最强开源系之一，多语言、8192 token 长文本
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_DIM = 1024


class BaseEmbeddingClient(ABC):
    """嵌入客户端抽象。注意接口是批量的；`embed_one` 只是批量的单元素便捷方法。"""

    model_name: str = ""
    dim: int = 0

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """一批文本 → 一批向量，顺序与输入一一对应。"""

    async def embed_one(self, text: str) -> list[float]:
        """查询侧的单条便捷方法。"""
        return (await self.embed([text]))[0]


class FakeEmbeddingClient(BaseEmbeddingClient):
    """确定性「字符 n-gram 哈希向量」：离线可跑、零成本、可重现。

    它替代不了真实模型的语义能力，但能验证三件事（03 §3.4）：
        接口契约（批量 / 顺序 / 维度）、向量库的存取与排序、RAG 流水线的串联。

    算法（刻意做到「确定 + 语义相关」）：
        1. 逐字（unigram）与逐字相邻对（bigram）各落一个哈希桶计数；
        2. tf 取 1 + log(tf)，压一压"的了"这类高频虚词；
        3. L2 归一化后取余弦 —— 共享字面越多的两段文本，向量夹角越小。
    确定性靠 hashlib（md5），**不用** Python 内建 hash()（它有随机化种子，
    同一次进程内两次结果不同，测试会抽风）。
    """

    model_name = "fake-char-ngram"
    dim = 64

    def __init__(self, dim: int = 64):
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_vector(t) for t in texts]

    def _hash_vector(self, text: str) -> list[float]:
        buckets = [0.0] * self.dim
        chars = [ch for ch in text.lower() if not ch.isspace()]
        for ch in chars:
            buckets[self._bucket(ch)] += 1.0
        for a, b in zip(chars, chars[1:]):
            buckets[self._bucket(a + b)] += 1.0
        # 子线性：字频高的字不该压过实义词
        return normalize([1.0 + math.log(v) if v > 0 else 0.0 for v in buckets])

    def _bucket(self, item: str) -> int:
        """字符串 → [0, dim) 的稳定桶号。"""
        digest = hashlib.md5(item.encode("utf-8")).digest()[:4]
        return int.from_bytes(digest, "big") % self.dim


class _OpenAIStyleEmbeddingClient(BaseEmbeddingClient):
    """OpenAI `/v1/embeddings` 协议客户端的公共骨架（httpx 异步 + 分批 + 指数退避）。

    为什么要抽这一层（11 章展开）：SiliconFlow、阿里云百炼、OpenAI、乃至你自己
    vLLM 部署的 bge，实现的都是**同一套协议** ——
        请求 {"model": ..., "input": [...]}
        响应 {"data": [{"index": i, "embedding": [...]}, ...]}
    差异只有三样：base_url、模型名、单批上限。
    于是协议细节（分批 / 按 index 还原顺序 / 429 指数退避 / 错误分层）只写一遍，
   「换云厂商」= 复制三行子类。**这是接入真实服务时最值钱的 20 行代码。**

    子类只需声明 5 个类属性：
        BASE_URL / ENV_VAR / model_name / dim / DEFAULT_BATCH_SIZE

    两个容易忽略的细节（03 §3.3）：
        - 响应里按 `index` 字段重新排序（有的服务不保证返回顺序与请求一致）；
        - 429 用指数退避（1s → 2s → 4s）重试，而不是立刻打回去（雪崩）。

    注意本项目不鼓励在测试里触达这里：单测一律用 FakeEmbeddingClient。
    """

    BASE_URL: str = ""
    ENV_VAR: str = ""              # 没传 api_key 时，从哪个环境变量兜底
    model_name: str = ""
    dim: int = 0
    DEFAULT_BATCH_SIZE: int = 32
    MAX_RETRIES: int = 3
    TIMEOUT: float = 30.0
    MAX_CHARS: int = 8000          # 单条最长字符数，超出直接截断（03 坑 3）

    def __init__(self, api_key: str | None = None, model: str = "",
                 batch_size: int | None = None):
        key = api_key or os.getenv(self.ENV_VAR, "")
        if not key:
            raise EmbeddingError(
                f"api_key 为空，无法调用 embedding 接口 —— 显式传入，"
                f"或设置环境变量 {self.ENV_VAR}"
            )
        self.api_key = key
        self.model_name = model or self.model_name
        self.batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        # 计量：demo / 文档要靠它证明「批量接口省了多少次往返」（11 章）
        self.request_count = 0
        self.latencies: list[float] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """核心契约：输入 n 条文本，返回 n 个向量，顺序与输入一一对应。"""
        if not texts:
            return []
        vectors: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = [t[:self.MAX_CHARS] for t in texts[i:i + self.batch_size]]
            vectors.extend(await self._embed_batch_with_retry(batch))
        if len(vectors) != len(texts):
            raise EmbeddingError(
                f"向量条数与输入不一致: {len(texts)} 条文本 → {len(vectors)} 个向量")
        return vectors

    async def _embed_batch_with_retry(self, batch: list[str]) -> list[list[float]]:
        delay = 1.0
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return await self._embed_batch(batch)
            except EmbeddingRateLimitError:
                if attempt == self.MAX_RETRIES:
                    raise
                await _sleep(delay)      # 指数退避
                delay *= 2
        raise EmbeddingError("重试次数耗尽")  # pragma: no cover - 理论上到不了

    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        import time

        import httpx

        started = time.perf_counter()
        self.request_count += 1
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model_name, "input": batch},
            )
        self.latencies.append(time.perf_counter() - started)
        if resp.status_code == 429:
            raise EmbeddingRateLimitError("embedding 触发限流（429）")
        if resp.status_code in (401, 403):
            raise EmbeddingError(f"embedding 认证失败（{resp.status_code}）")
        resp.raise_for_status()
        try:
            data = resp.json()["data"]
        except Exception as e:  # noqa: BLE001 - 转成自己的异常层级
            raise EmbeddingError(f"embedding 响应结构异常: {resp.text[:200]}") from e
        # 按 index 还原顺序（03 坑 4）
        data = sorted(data, key=lambda d: d["index"])
        return [item["embedding"] for item in data]


class SiliconFlowEmbeddingClient(_OpenAIStyleEmbeddingClient):
    """SiliconFlow 托管 bge 系列（httpx）。中文最强开源系之一，多语言、8192 长文本。"""

    BASE_URL = "https://api.siliconflow.cn/v1/embeddings"
    ENV_VAR = "SILICONFLOW_API_KEY"
    model_name = DEFAULT_EMBEDDING_MODEL
    dim = DEFAULT_DIM
    DEFAULT_BATCH_SIZE = 32


class DashScopeEmbeddingClient(_OpenAIStyleEmbeddingClient):
    """阿里云百炼（DashScope）compatible-mode 兼容接口。

    为什么有它：百炼是国内最容易跑通「注册 → 拿 key → 出向量」的一站式平台，
    形如 text-embedding-v3 的模型与 bge-m3 同族，**默认 1024 维**，和
    SiliconFlow 的 bge-m3 对齐 —— 这意味着 04 章讲的 Chroma 维度不用改。

    两个实测结论（11 章有截图证据）：
        1. 单批上限 10 条：超过会直接报错，所以 DEFAULT_BATCH_SIZE 必须比
           SiliconFlow 那家更小 —— **别把 batch_size 当成全局常数**。
        2. 响应体的 data 带 index，别假设顺序，老老实实排序。

    百炼还有一套非兼容的老接口 /api/v1/services/aigc/...，
    这里只用 compatible-mode（OpenAI 兼容），因为换 provider 的成本才是我们要练的。
    """

    BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    ENV_VAR = "DASHSCOPE_API_KEY"
    model_name = "text-embedding-v3"
    dim = 1024
    DEFAULT_BATCH_SIZE = 10


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def create_embedding_client(provider: str = "fake", **kwargs) -> BaseEmbeddingClient:
    """客户端工厂：上层（入库流水线）只依赖 BaseEmbeddingClient。"""
    if provider == "fake":
        return FakeEmbeddingClient(**kwargs)
    if provider == "siliconflow":
        return SiliconFlowEmbeddingClient(**kwargs)
    if provider == "dashscope":
        return DashScopeEmbeddingClient(**kwargs)
    raise EmbeddingError(
        f"未知 embedding provider: {provider!r}（可选 fake / siliconflow / dashscope）")
