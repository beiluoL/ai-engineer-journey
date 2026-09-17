"""Lesson 02 — List / Dict / AI Messages Demo（预告结构，待学习时完善）。

这一课的核心：理解 LLM API 的 messages 数据结构。
messages = list[dict]：list 里装 dict，这就是后续所有 LLM 项目的地基。
"""

# === AI Messages：list + dict 的嵌套结构 ===
messages = [
    {
        "role": "system",
        "content": "你是我的 Python 老师"
    },
    {
        "role": "user",
        "content": "什么是 list？"
    }
]

# 打印每条消息
for msg in messages:
    print(f"[{msg['role']}] {msg['content']}")

# 这就是一次 LLM API 调用请求体的核心部分
