"""Chapter 07 演示：token 估算、1 token 等于多少字符、上下文占用条、成本。

跑法（在 `projects/03-ai-application` 目录下）：

    PYTHONPATH=src python3 demos/token_stats.py

全程离线：不联网、不需要 API Key。
如果环境里装了 `tiktoken`，会自动多打一列「精确 token」做对比；
没装则只打项目自己的 `estimate_tokens()` 估算值。
"""

from __future__ import annotations

from assistant.memory import Conversation
from assistant.tokens import Budget, cost_cny, estimate_messages_tokens, estimate_tokens

# 三段用来对比的文本：纯中文 / 纯英文 / 中英混排
TEXTS = {
    "中文": "今天天气不错，我们一起出去走走吧。",
    "英文": "The quick brown fox jumps over the lazy dog.",
    "混排": "把 FastAPI 里的 client.chat 改成 messages 列表，报错就没了。",
}

# 演示用的一轮对话内容
USER_TEXT = "记一下背景：我调用 client.chat 报错说缺少参数 messages，但本地 pytest 是全绿的。"
BOT_REPLY = "结论是接口层和客户端层的签名不一致：单测直接调客户端，覆盖不到接口层，改成 messages 列表即可。"

# 官方单价（元 / 百万 token）—— 示例值，以厂商官网为准
PRICE_IN, PRICE_OUT = 1.0, 2.0


def load_tiktoken():
    """有 tiktoken 就用它做精确对比，没有就返回 None（不编数字）。"""
    try:
        import tiktoken  # type: ignore
    except ImportError as e:
        return None, f"捕捉到 {type(e).__name__}"
    try:
        return tiktoken.get_encoding("cl100k_base"), ""
    except Exception as e:  # 首次使用需要联网下载词表
        return None, f"取词表失败：{type(e).__name__}"


def bar(ratio: float, width: int = 46) -> str:
    """把占用比例画成 ASCII 进度条。"""
    filled = min(width, int(ratio * width + 0.5))
    return "#" * filled + "." * (width - filled)


def main() -> None:
    enc, reason = load_tiktoken()

    # ---- 1. 三段文本的字符 / 字节 / 估算 token ----
    print("=== 1. 同样一段意思，中文和英文的 token 差多少 ===")
    for name, text in TEXTS.items():
        chars = len(text)
        tokens = estimate_tokens(text)
        real_txt = f" / 精确 token {len(enc.encode(text))}" if enc else ""
        print(f"  [{name}] {text}")
        print(f"    字符数 {chars} / UTF-8 字节 {len(text.encode('utf-8'))} / 估算 token {tokens}{real_txt}")
        print(f"    1 token ≈ {chars / tokens:.2f} 个字符（用字符数当 token 会多算 {chars / tokens:.2f} 倍）")

    # ---- 2. 与真实分词器对比（有 tiktoken 才打）----
    print("\n=== 2. 与真实分词器对比 ===")
    if enc is None:
        print("  跳过精确对比：本机没有可用的 tiktoken")
        print(f"#   {reason}；装上后（pip install tiktoken）本节会自动打印精确 token 与估算的误差")
    else:
        for name, text in TEXTS.items():
            est, real = estimate_tokens(text), len(enc.encode(text))
            print(f"  [{name}] 估算 {est} vs 精确 {real} → 误差 {abs(est - real) / real * 100:.0f}%")

    # ---- 3. 上下文占用条：输入与输出共享同一个窗口 ----
    print("\n=== 3. 上下文占用条（输入与输出共享同一个窗口）===")
    budget = Budget(context_window=64_000, reserved_output=2_048, history_ratio=0.6)
    print(f"  窗口 {budget.context_window:,} token / 预留输出 {budget.reserved_output:,}"
          f" / 历史预算 {budget.history_budget:,}")
    for rounds in (0, 5, 50, 200):
        conv = Conversation(system_prompt="你是一个简洁、耐心的中文 AI 助手。")
        for i in range(rounds):
            conv.add_user(f"第 {i + 1} 轮：{USER_TEXT}")
            conv.add_assistant(BOT_REPLY)
        used = estimate_messages_tokens(conv.to_messages())
        print(
            f"  {rounds:>3} 轮 {bar(used / budget.context_window)}"
            f" {used / budget.context_window * 100:5.1f}%  {used:,} token"
        )
    print("  → 窗口是共享的：历史占满后，留给本次回答的空间会被挤到 0")

    # ---- 4. 成本：O(n²) 是怎么来的 ----
    print("\n=== 4. 成本（示例单价：输入 1 元 / 输出 2 元 每百万 token）===")
    per_round_in = estimate_tokens(USER_TEXT) + estimate_tokens(BOT_REPLY)
    out_tokens = estimate_tokens(BOT_REPLY)
    one = cost_cny("deepseek-chat", per_round_in, out_tokens)
    print(f"  单轮新增历史 ≈ {per_round_in} token")
    print(f"  第 1 轮（没有历史）：输入 {per_round_in} + 输出 {out_tokens} token → {one:.6f} 元")
    for rounds in (10, 30):
        total_in = per_round_in * rounds * (rounds + 1) // 2      # 每轮都要重发全部历史
        total_out = out_tokens * rounds
        print(
            f"  {rounds:>2} 轮累计：输入 {total_in:,} token + 输出 {total_out:,} token"
            f" → {cost_cny('deepseek-chat', total_in, total_out):.4f} 元"
            f"（{rounds * (rounds + 1) // 2} 倍单轮输入）"
        )
    print(f"  单价对比：输出比输入贵 {PRICE_OUT / PRICE_IN:.0f} 倍，所以「让模型少说废话」直接省钱")


if __name__ == "__main__":
    main()
