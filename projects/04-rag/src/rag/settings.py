"""集中式配置（对应 milestone 09 §3.2）。

三条铁律（沿用 P02/P03）：

1. 配置集中在一处 —— 想知道「这个项目要配什么」只看这个文件
2. frozen —— 启动时读一次，之后谁也改不了；要改就用 `replace()` 生成新对象
3. 不在模块顶层读环境变量 —— 否则 import 就崩，连 pytest 都跑不起来

RAG 比 chat 多的是索引侧参数（chunk_size / chunk_overlap / top_k / rerank_top_n）
与预算参数（budget_tokens / context_window / reserved_output）。
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .errors import ConfigurationError

# profile 表：不同场景用不同口味（和 P02/P03 的 PROFILES 同款）
PROFILES: dict[str, dict[str, object]] = {
    # 离线 demo / 单测：关 rerank（不调外部 API），预算收小逼出裁剪逻辑
    "test": {"enable_rerank": False, "budget_tokens": 800, "context_window": 2000,
             "reserved_output": 512},
    # 本地小规模知识库：默认全开
    "dev": {},
}


@dataclass(frozen=True)
class RAGSettings:
    """RAG 的全部配置。frozen = 不可变，多处传递时不会被谁悄悄改掉。"""

    # —— 索引侧（02 章）——
    chunk_size: int = 500
    chunk_overlap: int = 80
    # —— 检索侧（05 章）——
    top_k: int = 5
    fetch_k: int = 20          # 粗召回条数，rerank / mmr 的输入
    hybrid: bool = True        # 是否启用混合检索（vector + 关键词 RRF 融合）
    mmr: bool = False          # 是否开启最大边际相关性（多样性）
    # —— 精排侧（07 章）——
    enable_rerank: bool = True
    rerank_top_n: int = 5
    # —— 组装侧（08 章）——
    min_score: float = 0.2     # 低于该分数视为噪声，不进 prompt
    budget_tokens: int = 6000  # 本次问答能给【参考资料】用的 token 预算
    context_window: int = 64_000
    reserved_output: int = 2_048
    # —— 模型侧 ——
    embedding_model: str = "BAAI/bge-m3"

    @classmethod
    def for_profile(cls, profile: str = "dev") -> "RAGSettings":
        """按 profile 生成配置。未知 profile 直接抛错，不静默退回默认值。"""
        if profile not in PROFILES:
            raise ConfigurationError(
                f"未知 profile: {profile!r}（可选 {sorted(PROFILES)}）"
            )
        return cls(**PROFILES[profile])  # type: ignore[arg-type]

    def replace(self, **changes) -> "RAGSettings":
        """返回改了某几个字段的新对象；原对象不动（frozen 的意义）。

        Java 类比：wither / builder 产出的不可变副本。
        """
        return replace(self, **changes)

    def effective_budget(self) -> int:
        """给【参考资料】的实际预算 = min(budget_tokens, 窗口 - 给输出留的)。

        08 章的总预算公式：context_window - reserved_output - estimate_tokens(system)。
        budget_tokens 是「这次问答愿意花多少」的上限，窗口是物理上限，两者取小。
        """
        return max(min(self.budget_tokens, self.context_window - self.reserved_output), 0)

    def validate(self) -> "RAGSettings":
        """入口处把守参数约束（02 章坑 5：overlap >= size 会死循环）。"""
        if self.chunk_size <= 0:
            raise ConfigurationError(f"chunk_size 必须为正，当前 {self.chunk_size}")
        if self.chunk_overlap < 0:
            raise ConfigurationError(
                f"chunk_overlap 不能为负，当前 {self.chunk_overlap}")
        if self.chunk_overlap >= self.chunk_size:
            raise ConfigurationError(
                f"chunk_overlap({self.chunk_overlap}) 必须小于 chunk_size"
                f"({self.chunk_size})，否则切分步长 <= 0，会死循环"
            )
        if self.top_k <= 0:
            raise ConfigurationError(f"top_k 必须为正，当前 {self.top_k}")
        return self
