"""RAG 的异常层级。

沿用 P02/P03 的 LLMError 风格：把「外部世界的不确定性」翻译成「本项目自己的语言」，
上层只想写 except RAGError，不需要知道是 PDF 解析失败还是 embedding 接口 429。

层级：
    RAGError
    ├── ConfigurationError     配置缺失 / 参数不合法（启动即失败，重试没用）
    ├── IngestionError         解析、读取文档失败（01 章）
    │   └── DependencyMissingError   pypdf / python-docx / chromadb 没装
    ├── EmbeddingError         向量化失败（03 章）
    │   └── EmbeddingRateLimitError  429，可指数退避后重试
    └── RetrievalError         检索 / 精排失败（05、07 章）
"""

from __future__ import annotations


class RAGError(Exception):
    """所有本项目异常的基类。上层写 except RAGError 即可兜住整条链路。"""


class ConfigurationError(RAGError):
    """配置错误：缺 Key、参数类型不对、profile 不存在。重试没用。"""


class IngestionError(RAGError):
    """摄入阶段失败：文件读不出来、格式不支持、解析抛错（01 章）。"""


class DependencyMissingError(IngestionError):
    """可选依赖没装（pypdf / python-docx / chromadb）。

    单独成一个类，是为了让调用方能区分「少个依赖」和「文件坏了」：
    前者提示 pip install，后者该进 skip 列表（09 章失败语义 1）。
    """

    def __init__(self, package: str, hint: str = "") -> None:
        self.package = package
        self.hint = hint
        super().__init__(f"缺少可选依赖 {package!r}。{hint} pip install {package}")


class EmbeddingError(RAGError):
    """向量化失败：请求失败、响应结构不对、维度不一致（03 章）。"""


class EmbeddingRateLimitError(EmbeddingError):
    """触发限流（HTTP 429）。可退避后重试（03 章坑 2）。"""


class RetrievalError(RAGError):
    """检索 / 精排阶段失败（05、07 章）。"""


class RerankError(RetrievalError):
    """精排失败（07 章）。降级路径是 NoopReranker。"""
