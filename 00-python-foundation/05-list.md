# 05 — List：列表

## 它是什么
有序可变的序列。Java 开发者直接理解成 `ArrayList`。

## 为什么需要它
Project 01 v0.2 的**连续对话**核心就是 list：把每轮消息追加进去发给 LLM。

## Java 开发者如何理解

```java
// Java
List<String> history = new ArrayList<>();
history.add("q1");
for (String h : history) { ... }
```

```python
# Python
history = []            # 不用泛型声明
history.append("q1")
for h in history: ...
```

## 核心操作（AI 项目高频）

```python
messages = []                                   # 空列表
messages.append({"role": "user", "content": "hi"})   # 追加，Java: add
messages.insert(0, {...})                       # 插入，Java: add(0, x)
len(messages)                                   # 长度
messages[0]                                     # 索引，越界会 IndexError
messages[-1]                                    # 最后一个！负索引是 Python 特色
messages[0:2]                                   # 切片 slice：取 [0,2)，Java 没有
messages.pop()                                  # 弹出末尾
[...,"a"] + ["b"]                               # 拼接生成新列表
```

**切片 slice** 必须掌握：`lst[start:stop:step]`，含头不含尾。

```python
nums = [0, 1, 2, 3, 4, 5]
nums[1:4]    # [1, 2, 3]
nums[:3]     # [0, 1, 2]
nums[-2:]    # [4, 5] —— 取最后两个
nums[::-1]   # 反转
```

## 最小可运行 Demo

```python
# demo_list.py —— 模拟对话历史（v0.2 的雏形）
history = []
history.append({"role": "user", "content": "什么是 Token？"})
history.append({"role": "assistant", "content": "Token 是模型处理文本的最小单位..."})
history.append({"role": "user", "content": "那 Embedding 呢？"})

print(f"共 {len(history)} 条消息")
print("第一条:", history[0]["content"])
print("最后一条:", history[-1]["content"])

# 只看用户的问题
for m in history:
    if m["role"] == "user":
        print("用户问:", m["content"])
```

## 常见错误

1. **越界**：`history[10]` → `IndexError`（Java 是 IndexOutOfBoundsException，一样要防）。
2. **可变默认参数陷阱**（面试高频）：`def f(history=[])` —— 默认列表在多次调用间**共享**！正确写法 `def f(history=None): history = history or []`。
3. **深浅拷贝**：`b = a` 只是引用同一个列表，改 b 连 a 一起变（同 Java）。要独立副本用 `a.copy()` 或切片 `a[:]`。
4. **append 返回 None**：`a = a.append(x)` ❌ —— append 原地修改返回 None，直接 `a.append(x)`。

## 常见面试问题
- list 和 tuple 区别？→ tuple 不可变 `(1, 2)`，可做 dict 的 key；list 可变。
- 如何复制列表？→ `copy()` / `list(a)` / 切片 `a[:]`（都是浅拷贝）。

## 练习
1. 建 list 存 5 门想学的技术，打印第 2 门和最后一门。
2. 用切片取出前 3 门。
3. 模拟三轮对话 history（list of dict）并遍历打印用户消息。

[下一课：06-dict →](06-dict.md)
