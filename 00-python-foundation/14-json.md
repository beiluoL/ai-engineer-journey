# 14 — JSON：序列化

## 它是什么
JSON 是程序间交换数据的事实标准。**LLM API 的请求体和响应体全是 JSON**——这一课直接决定你能不能看懂 AI 代码。

## Java 开发者如何理解

| Java (Jackson) | Python (json) |
|-----------------|---------------|
| `objectMapper.writeValueAsString(obj)` | `json.dumps(obj)`（dumps = dump to string） |
| `objectMapper.readValue(s, Map.class)` | `json.loads(s)`（loads = load from string） |
| 写文件 `writeValue(file, obj)` | `json.dump(obj, f)` |
| 读文件 `readValue(file, Map.class)` | `json.load(f)` |

记忆法：**带 s 操作字符串，不带 s 操作文件**。

## dict ↔ JSON：天然对应

```python
import json

payload = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": False,
}

body = json.dumps(payload, ensure_ascii=False)   # dict → JSON 字符串（HTTP 请求体）
print(body)

resp_text = '{"content": "你好！有什么可以帮你？", "usage": {"total_tokens": 15}}'
data = json.loads(resp_text)                     # JSON 字符串 → dict（HTTP 响应解析）
print(data["content"], data["usage"]["total_tokens"])
```

**`ensure_ascii=False` 必须记住**：默认 `True` 会把中文变成 `\u4f60\u597d` 之类的转义。

## 最小可运行 Demo

```python
# demo_json.py —— 保存/加载对话历史（v0.5 真实版）
import json
from pathlib import Path

history = [
    {"role": "user", "content": "什么是 RAG？"},
    {"role": "assistant", "content": "检索增强生成：先查资料再回答。"},
]

path = Path("history.json")
path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

loaded = json.loads(path.read_text(encoding="utf-8"))
assert loaded == history
print(f"成功保存并恢复 {len(loaded)} 条消息")
print(json.dumps(loaded[0], ensure_ascii=False))
```

## 常见错误

1. **中文变 \uXXXX**：忘了 `ensure_ascii=False`。
2. **dumps/loads 用反**：操作字符串用带 s 的，操作文件流用 `json.dump(obj, f)` / `json.load(f)`。
3. **dumps 含不可序列化对象**：`datetime`、自定义类直接 `TypeError`（Java 的 Jackson 有注解，Python 要自定义 `default=` 参数）。
4. **把 JSON 字符串当 dict 用**：`resp.text["content"]` ❌ —— HTTP 响应要先 `json.loads(resp.text)`。
5. **键必须是字符串**：`json.dumps({1: "a"})` 会把 int 键转成 "1"，读回类型变了。

## 常见面试问题
- JSON 和 dict 什么关系？→ JSON 是文本格式，dict 是内存对象；`dumps/loads` 负责互转，类似 Jackson 的序列化/反序列化。
- SSE 流式响应里的 JSON 有什么特殊？→ 每个数据块是一行 `data: {...}`，需要按行解析（v0.3 会遇到）。

## 练习
1. 把一个含中文的请求体 dict dumps 成合法 JSON 字符串。
2. 写"保存历史到 JSON 文件 + 读取恢复"一对函数。
3. 解析字符串 `{"choices": [{"message": {"content": "ok"}}]}` 取出 content（模拟真实 API 响应）。

[下一课：15-env →](15-env.md)
