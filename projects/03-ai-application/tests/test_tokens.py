"""Token 估算与预算测试（milestones/07）。"""

from assistant.tokens import Budget, cost_cny, estimate_messages_tokens, estimate_tokens


def test_empty_text_is_zero():
    assert estimate_tokens("") == 0


def test_chinese_costs_more_per_char_than_english():
    """中文是这里的重点：同样意思，中文更费 token。"""
    zh = estimate_tokens("你好世界")
    en = estimate_tokens("hello world")
    assert zh >= 3
    assert en >= 2
    assert zh / len("你好世界") > en / len("hello world")


def test_estimate_is_not_character_count():
    text = "深度学习模型的注意力机制"
    assert estimate_tokens(text) != len(text)


def test_estimate_messages_includes_overhead():
    msgs = [{"role": "user", "content": "你好"}]
    assert estimate_messages_tokens(msgs) > estimate_tokens("你好")


def test_budget_verdicts():
    b = Budget(context_window=1000, reserved_output=200, history_ratio=0.5)
    assert b.history_budget == 400          # (1000-200)*0.5
    assert b.check(100) == "ok"
    assert b.check(500) == "trim"
    assert b.check(900) == "overflow"       # 1000-200=800 是硬上限


def test_cost_increases_with_tokens():
    assert cost_cny("deepseek-chat", 1_000_000, 0) == 1.0
    assert cost_cny("deepseek-chat", 0, 1_000_000) == 2.0
    assert cost_cny("unknown-model", 1000, 1000) > 0
