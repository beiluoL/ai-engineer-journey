"""Token 估算与成本预算（对应 milestones/07-token-context-window.md）。

两条铁律：

1. **估算用来做决策**（要不要裁剪历史），不用来做计费
2. **计费一律用响应里的 usage**（prompt_tokens / completion_tokens）

中文是这里的重点：1 个汉字通常接近 1 个 token，
所以「按字符数估算」在中文场景下会差出好几倍。
"""

from __future__ import annotations

from dataclasses import dataclass

# 每百万 token 的单价（元）。示例值，请以厂商官网为准。
PRICE_PER_MTOK: dict[str, dict[str, float]] = {
    "deepseek-chat": {"in": 1.0, "out": 2.0},
    "deepseek-reasoner": {"in": 2.0, "out": 8.0},
}
DEFAULT_PRICE = {"in": 1.0, "out": 2.0}


def estimate_tokens(text: str) -> int:
    """粗估一段文本的 token 数。

    规则（够做预算决策用）：
    - 中日韩字符：每个约 0.9 token
    - 其他（英文、数字、标点）：每 3.5 个字符约 1 token
    """
    if not text:
        return 0
    cjk = sum(
        1
        for ch in text
        if "\u4e00" <= ch <= "\u9fff"          # CJK 统一汉字
        or "\u3040" <= ch <= "\u30ff"          # 日文假名
        or "\uac00" <= ch <= "\ud7af"          # 韩文
    )
    other = len(text) - cjk
    return int(cjk * 0.9 + other / 3.5) + 1


def estimate_messages_tokens(messages: list[dict]) -> int:
    """估算整个 messages 数组的 token 数（含 role 等结构开销）。"""
    total = 0
    for m in messages:
        total += 4                              # 每条消息的结构开销（经验值）
        for key, value in m.items():
            total += estimate_tokens(str(key)) + estimate_tokens(str(value))
    return total


def cost_cny(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """按模型单价估算一次调用的费用（元）。"""
    price = PRICE_PER_MTOK.get(model, DEFAULT_PRICE)
    return (prompt_tokens * price["in"] + completion_tokens * price["out"]) / 1_000_000


@dataclass(frozen=True)
class Budget:
    """上下文预算模型。

    关键认知：**窗口是输入与输出共享的**——
    历史占得越多，留给回答的就越少。
    """

    context_window: int = 64_000     # 模型总窗口
    reserved_output: int = 2_048     # 预留给本次回答
    history_ratio: float = 0.6       # 历史最多占剩余窗口的比例

    @property
    def history_budget(self) -> int:
        """历史（含 system）最多可用多少 token。"""
        usable = self.context_window - self.reserved_output
        return max(0, int(usable * self.history_ratio))

    def check(self, messages_tokens: int) -> str:
        """返回 'ok' / 'trim' / 'overflow'，供 service 决定怎么处理。"""
        if messages_tokens > self.context_window - self.reserved_output:
            return "overflow"
        if messages_tokens > self.history_budget:
            return "trim"
        return "ok"
