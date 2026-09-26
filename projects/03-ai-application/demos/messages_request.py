"""Chapter 02 演示：把一次多轮对话的**真实请求体**打印出来。

跑法（在 `projects/03-ai-application` 目录下）：

    PYTHONPATH=src python3 demos/messages_request.py

全程离线：只用 memory / tokens / settings / client 的纯逻辑，
不发起任何网络请求，也不需要真实 API Key。
"""

from __future__ import annotations

import json

from assistant.client import DeepSeekClient
from assistant.memory import Conversation, validate_messages
from assistant.settings import Settings
from assistant.tokens import estimate_messages_tokens, estimate_tokens


def main() -> None:
    # 占位 key：客户端只把它放进请求头，本 demo 不发起任何网络请求
    settings = Settings(api_key="local-fake-key-please-replace")

    # ---- 1. 用真实代码构造一段多轮 messages ----
    conv = Conversation(system_prompt="你是一个简洁、耐心的中文 AI 助手。")
    conv.add_user("我叫小明，写了 5 年 Java 后端。")
    conv.add_assistant("你好小明，想把它做成 AI 应用？")
    conv.add_user("对，想把简历里的技能抽成结构化数据。")
    # 模型这一轮不发正文，只发工具调用（Chapter 08 详讲）
    conv.add_assistant(
        "好的，我先调一次技能抽取工具。",
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "extract_skills", "arguments": "{}"},
            }
        ],
    )
    # 工具结果用 tool 角色回灌，靠 tool_call_id 对上上面那次调用
    conv.add_tool("call_1", '{"skills":["Java","Spring Boot"],"years":5}')
    conv.add_assistant("抽到了：Java、Spring Boot，工作 5 年。")

    messages = conv.to_messages()

    print("=== 1. 每条消息的角色与内容 ===")
    for i, m in enumerate(messages):
        content = m.get("content", "")
        if len(content) > 22:
            content = content[:22] + "…"
        name = ""
        if m.get("tool_calls"):
            name = " → tool_calls:" + m["tool_calls"][0]["function"]["name"]
        print(f"[{i}] {m['role']:<9} {content}{name}")

    # ---- 2. JSON 序列化（注意 ensure_ascii=False，否则中文会变 \uXXXX）----
    print("\n=== 2. 完整 messages 数组（json.dumps）===")
    print(json.dumps(messages, ensure_ascii=False, indent=2))

    # ---- 3. 发给模型的请求体，除 messages 之外的字段 ----
    client = DeepSeekClient(settings)
    payload = client.build_payload(messages)
    print("\n=== 3. 请求体里除 messages 之外的字段 ===")
    for key in ("model", "stream", "temperature", "top_p", "max_tokens"):
        print(f"  {key:<12} = {payload[key]}")

    # ---- 4. token 估算：messages 数组到底多大 ----
    total = estimate_messages_tokens(messages)
    chars = sum(len(m.get("content", "")) for m in messages)
    print("\n=== 4. token 估算 ===")
    print(f"  消息条数        = {len(messages)}")
    print(f"  正文字符数      = {chars}")
    print(f"  估算 token      = {total}（estimate_messages_tokens）")
    print(f"  含 role 开销后  = 1 个字符约 {total / chars:.2f} 个 token")

    # ---- 5. 校验器：role 拼错必须在发送前就炸 ----
    print("\n=== 5. 发送前校验（故意把 role 写成 AI）===")
    bad = [dict(m) for m in messages]
    bad[2]["role"] = "AI"
    try:
        validate_messages(bad)
    except ValueError as e:
        print(f"  ValueError: {e}")


if __name__ == "__main__":
    main()
