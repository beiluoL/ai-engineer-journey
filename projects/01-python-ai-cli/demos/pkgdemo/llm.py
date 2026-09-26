"""模拟一个 LLM 客户端（完全不联网，不需要 API Key）。"""


def chat(messages, model="gpt-4o-mini"):
    """把 messages 列表「发」给模型，返回一个假回复。

    真实项目里这里会变成 requests.post(...)，
    但这次我们要先学会怎么组织代码，所以先 mock 掉。
    """
    last_user = ""
    for m in messages:
        if m["role"] == "user":
            last_user = m["content"]
    last_user = last_user or "(空消息)"
    return {
        "role": "assistant",
        "content": f"[模拟回复] 你刚才问的是：{last_user}",
        "model": model,
    }


def count_messages(messages):
    """统计 messages 里每种 role 各有多少条。"""
    stats = {}
    for m in messages:
        role = m["role"]
        stats[role] = stats.get(role, 0) + 1
    return stats
