# 06 — Dict：字典

## 它是什么
键值对容器。Java 开发者理解成 `HashMap`，但 key 更自由（任何不可变类型）、字面量语法是日常主战场。

## 为什么需要它
**LLM API 的请求体就是 list of dict**：每条消息 `{"role": "user", "content": "..."}`。不懂 dict 就读不懂任何 LLM 调用代码。

## Java 开发者如何理解

```java
// Java
Map<String, Object> msg = new HashMap<>();
msg.put("role", "user");
msg.put("content", "hi");
```

```python
# Python —— 字面量直接写，这就是 AI 代码里最常见的形态
msg = {"role": "user", "content": "hi"}
msg["role"]          # 取值，key 不存在会 KeyError
msg.get("top_p")     # 取值，不存在返回 None，不报错（类似 getOrDefault）
```

## 核心操作（AI 项目高频）

```python
payload = {
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 1024,
    "stream": False,
}

payload["temperature"] = 0.7        # 新增/修改
del payload["max_tokens"]           # 删除
"model" in payload                  # 判断 key 存在
payload.keys() / .values() / .items()   # 遍历三件套

for k, v in payload.items():        # 同时遍历键值（比 Java entrySet 简洁）
    print(k, "=", v)

merged = {**defaults, **overrides}  # 字典合并，后者覆盖前者（Java: putAll）
```

## 最小可运行 Demo

```python
# demo_dict.py —— 构造一次真实的 LLM API 请求体
request = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "你是一个简洁的中文助手。"},
        {"role": "user", "content": "用一句话解释什么是 API"},
    ],
    "temperature": 0.7,
}

print(request["model"])
print(request["messages"][-1]["content"])   # dict 套 list 套 dict：AI 代码常态
print("temperature" in request)
print(request.get("top_p", "未设置"))         # 安全取值

# 动态追加一轮对话
request["messages"].append({"role": "assistant", "content": "API 是程序之间约定好的对话接口。"})
for m in request["messages"]:
    print(f'[{m["role"]}] {m["content"]}')
```

## 常见错误

1. **`KeyError`**：`d["不存在的key"]` 直接炸。读可能缺失的 key 一律用 `.get()`。
2. **用 `.append` 加键**：dict 没有 append，加键值直接 `d["k"] = v`。
3. **dict 无序的旧观念**：Python 3.7+ dict **保持插入顺序**（这一点和 Java HashMap 不同，和 LinkedHashMap 一样）。
4. **嵌套取值链断裂**：`d["a"]["b"]` 中 `d["a"]` 是 None 时会 `TypeError`，多层嵌套先 `.get("a", {})`。

## 常见面试问题
- dict 底层是什么？→ 哈希表，平均 O(1) 查找（同 Java HashMap）；所以 key 必须可哈希（不可变）。
- dict 和 list 怎么选？→ 按名字找东西用 dict，按顺序存一批用 list；LLM 消息历史 = list of dict，两者结合。

## 练习
1. 构造一个含 system + user 两条消息的请求体 dict。
2. 用 `.get()` 安全读取不存在的 `top_p`。
3. 用 `{**a, **b}` 合并默认配置与用户覆盖配置。

[下一课：07-if →](07-if.md)
