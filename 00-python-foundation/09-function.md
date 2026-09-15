# 09 — Function：函数

## 它是什么
可复用的代码块。Python 函数是**一等公民**：能赋值给变量、当参数传递（Java 8 之前做不到）。

## Java 开发者如何理解

```java
// Java：方法必须活在类里，必须声明返回类型
public String ask(String question) { return "..."; }
```

```python
# Python：函数独立存在，不声明返回类型，def 定义
def ask(question: str) -> str:
    return "..."
```

**关键差异**：
1. 函数不写返回类型也能返回任何东西（类型提示只是提示）。
2. 没写 `return` 的函数返回 `None`（不是 void，是真返回一个 None 对象）。
3. 支持**默认参数**和**关键字参数**，调用时可读性远超 Java 重载。

## 核心语法（AI 项目高频）

```python
def build_messages(question: str, history: list | None = None,
                   system_prompt: str = "你是一个简洁的中文助手。") -> list:
    """构造 LLM 请求的消息列表。默认参数减少重复调用代码。"""
    if history is None:          # 可变默认参数陷阱的标准规避写法
        history = []
    return [{"role": "system", "content": system_prompt}, *history,
            {"role": "user", "content": question}]

# 关键字调用：哪个参数是什么一目了然（Java 没有）
msgs = build_messages(question="什么是 RAG？", system_prompt="你是 Java 老兵转 AI 的助教")
```

**多返回值**：Python 函数可以直接返回元组——Java 得造个类：

```python
def parse_response(data: dict) -> tuple[str, int]:
    return data["content"], data["usage"]["total_tokens"]

answer, tokens = parse_response(resp)   # 解包接收
```

## 最小可运行 Demo

```python
# demo_function.py —— Project 01 的核心函数雏形
def build_messages(question: str, history: list | None = None) -> list[dict]:
    """把问题构造成 LLM API 需要的消息格式。"""
    if history is None:
        history = []
    messages = [{"role": "system", "content": "你是一个简洁的中文助手。"}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})
    return messages

def fake_call_llm(messages: list[dict]) -> dict:
    """假装调用 LLM（v0.1 会换成真实 HTTP 调用）。"""
    return {"role": "assistant", "content": f"已收到 {len(messages)} 条消息", "usage": {"total_tokens": 42}}

def answer(question: str) -> tuple[str, int]:
    """提问 → 回答 + token 用量。"""
    resp = fake_call_llm(build_messages(question))
    return resp["content"], resp["usage"]["total_tokens"]

text, tokens = answer("什么是 Embedding？")
print(f"{text}（消耗 {tokens} tokens）")
```

## 常见错误

1. **可变默认参数**：`def f(history=[])` —— 默认值只创建一次，多次调用共享！永远用 `None` + 函数内重建。
2. **忘记 return**：函数里算了半天结果没 return，拿到的是 None。
3. **默认参数放在非默认参数前面**：`def f(a=1, b)` → SyntaxError，默认参数必须靠右。
4. **把方法调用当副作用链**：`msgs.append(x).something()` —— append 返回 None，不能链式。

## 常见面试问题
- Python 传参是值传递还是引用传递？→ 都不是，是"传对象引用"：传可变对象（list/dict）函数内能改到原对象，传不可变对象（int/str）表现像值传递。
- `*args` / `**kwargs`？→ 收集位置参数为元组、关键字参数为字典，用于写包装器/代理函数。

## 练习
1. 写 `build_payload(question, model, temperature)` 返回完整请求体 dict。
2. 写一个函数返回 `(回复, token数)` 元组并解包。
3. 故意写一个可变默认参数 bug 并观察共享现象，然后修复。

[下一课：10-module →](10-module.md)
