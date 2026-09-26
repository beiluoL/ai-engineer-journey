"""Chapter 06 演示：模型参数到底改了什么。

跑法（在 `projects/03-ai-application` 目录下）：

    PYTHONPATH=src python3 demos/model_params.py

三部分：
1. 用真实的 `Settings.for_profile()` + `DeepSeekClient.build_payload()` 打印请求体
2. 在本地复现采样算法（softmax / top_p / presence_penalty）——**不是模型输出**，
   只是同一套数学，用来看清每个参数在改什么
3. 用 `estimate_tokens()` 算 `max_tokens` 太小会在哪里截断

全程离线，不联网、不需要 API Key。
"""

from __future__ import annotations

import asyncio
import math

from assistant.client import DeepSeekClient
from assistant.settings import PROFILES, Settings
from assistant.tokens import estimate_tokens

# 一条普通的用户提问（各 profile 都用它）
MESSAGES = [
    {"role": "system", "content": "你是一个简洁、耐心的中文 AI 助手。"},
    {"role": "user", "content": "把这份简历里的技能抽成 JSON。"},
]

# 固定的候选词与「原始打分」：本地复现采样算法用的输入
LOGITS = {"答案": 3.2, "结论": 2.6, "可能": 2.0, "也许": 1.2, "不好说": 0.5}


def softmax(logits: dict[str, float], temperature: float) -> dict[str, float]:
    """按 temperature 把原始打分变成概率分布（temperature=0 即贪心）。"""
    if temperature <= 0:
        best = max(logits, key=lambda k: logits[k])
        return {k: (1.0 if k == best else 0.0) for k in logits}
    exps = {k: math.exp(v / temperature) for k, v in logits.items()}
    total = sum(exps.values())
    return {k: v / total for k, v in exps.items()}


def top_p_filter(probs: dict[str, float], top_p: float) -> list[str]:
    """核采样：按概率从大到小累加，累计到 top_p 就截断，只留这些候选。"""
    kept: list[str] = []
    cum = 0.0
    for word, p in sorted(probs.items(), key=lambda kv: -kv[1]):
        kept.append(word)
        cum += p
        if cum >= top_p:
            break
    return kept


def apply_presence_penalty(
    logits: dict[str, float], seen: set[str], penalty: float
) -> dict[str, float]:
    """presence_penalty：已经出现过的话题，下次打分直接减一个固定值。"""
    return {k: (v - penalty if k in seen else v) for k, v in logits.items()}


async def main() -> None:
    base = Settings(api_key="local-fake-key")

    # ---- 1. 真实的请求体：PROFILES 如何覆盖参数 ----
    print("=== 1. 同一段 messages，四个场景的真实请求体 ===")
    clients: list[DeepSeekClient] = []
    for name in ("extract", "code", "chat", "creative"):
        settings = base.for_profile(name)
        client = DeepSeekClient(settings)
        clients.append(client)
        payload = client.build_payload(MESSAGES)
        print(
            f"  {name:<9} temperature={payload['temperature']:<4}"
            f" top_p={payload['top_p']:<4} max_tokens={payload['max_tokens']}"
        )
    print(f"  原始默认值：temperature={base.temperature} top_p={base.top_p} max_tokens={base.max_tokens}")
    print(f"  PROFILES 里可选的场景：{', '.join(PROFILES)}")
    for client in clients:
        await client.aclose()

    # ---- 2. 本地复现采样算法（不是模型输出）----
    print("\n=== 2. temperature 改了什么（对同一份原始打分做 softmax）===")
    print("  原始打分：" + "  ".join(f"{k}={v}" for k, v in LOGITS.items()))
    for t in (0.0, 0.7, 1.2):
        probs = softmax(LOGITS, t)
        top_word = max(probs, key=lambda k: probs[k])
        kept = top_p_filter(probs, 0.9)
        print(
            f"  temperature={t:<4} 最高概率词={top_word}({probs[top_word]:.2f})"
            f"  概率分布={{{', '.join(f'{k}:{v:.2f}' for k, v in probs.items())}}}"
        )
        print(f"                top_p=0.9 过滤后只剩 {len(kept)} 个候选：{'、'.join(kept)}")

    print("\n=== 3. presence_penalty 改了什么（「答案」已经说过一次）===")
    for penalty in (0.0, 1.5):
        logits = apply_presence_penalty(LOGITS, seen={"答案"}, penalty=penalty)
        probs = softmax(logits, 0.7)
        top_word = max(probs, key=lambda k: probs[k])
        print(
            f"  penalty={penalty:<4} 最高概率词={top_word}({probs[top_word]:.2f})"
            f"  「答案」的概率={probs['答案']:.2f}"
        )

    # ---- 4. max_tokens 太小会截断在哪 ----
    print("\n=== 4. max_tokens 决定输出会不会被截断 ===")
    reply = (
        "结论：接口层和客户端层的函数签名不一致。单测直接调客户端所以覆盖不到接口层。"
        "改法是把接口入参改成 messages 列表，或者让客户端接受 text 并自己拼 messages。"
        "验证方式是补一个走 HTTP 的集成测试，而不是只补单元测试。"
        "另外注意 finish_reason 为 length 时就是被截断了。"
    ) * 2
    total = estimate_tokens(reply)
    print(f"  这段回复估算 = {total} token（{len(reply)} 个字符）")
    for max_tokens in (128, 512, 2048):
        if total > max_tokens:
            print(f"  max_tokens={max_tokens:>5} → 会被截断，finish_reason=length，尾部 {total - max_tokens} token 丢掉")
        else:
            print(f"  max_tokens={max_tokens:>5} → 完整输出，还剩 {max_tokens - total} token 余量")


if __name__ == "__main__":
    asyncio.run(main())
