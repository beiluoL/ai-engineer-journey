# 08 — For：循环

## 它是什么
Python 的 for 是 **for-each**（遍历可迭代对象），没有 Java 的三段式 `for(int i=0;...)`。

## Java 开发者如何理解

```java
// Java
for (int i = 0; i < 3; i++) { System.out.println(i); }
for (String s : list) { ... }
```

```python
# Python
for i in range(3): print(i)      # range(3) = 0,1,2 —— 相当于三段式
for s in list_: print(s)         # 相当于增强 for
```

## 核心用法（AI 项目高频）

```python
# 遍历消息历史
for msg in messages:
    print(msg["role"], msg["content"])

# 需要下标时用 enumerate（Java 的 i + list.get(i) 合体）
for i, msg in enumerate(messages, start=1):
    print(f"{i}. [{msg['role']}] {msg['content']}")

# 同时遍历两个列表：zip
for q, a in zip(questions, answers):
    print(q, "->", a)

# 重试 N 次（v0.7 API 重试的原型）
for attempt in range(1, 4):
    print(f"第 {attempt} 次尝试...")

# 列表推导式（Python 招牌，Java Stream 的极简版）
roles = [m["role"] for m in messages]                 # Java: map
user_msgs = [m for m in messages if m["role"] == "user"]  # Java: filter
lengths = [len(m["content"]) for m in messages]
```

**while** 也在：交互式 CLI 的主循环就是 `while True:` + `break`。

## 最小可运行 Demo

```python
# demo_for.py —— 打印对话 + 简易重试骨架
messages = [
    {"role": "user", "content": "什么是 Token？"},
    {"role": "assistant", "content": "模型处理文本的最小单位。"},
    {"role": "user", "content": "和字符有什么区别？"},
]

for i, m in enumerate(messages, start=1):
    print(f"{i}. [{m['role']}] {m['content']}")

# 模拟 API 重试（遇到 break 提前退出）
import random
for attempt in range(1, 4):
    ok = random.random() > 0.3
    if ok:
        print(f"第 {attempt} 次成功")
        break
    print(f"第 {attempt} 次失败，重试...")

# 推导式：提取所有用户问题
questions = [m["content"] for m in messages if m["role"] == "user"]
print("用户的问题:", questions)
```

## 常见错误

1. **找三段式 for**：Python 没有；要下标用 `enumerate`，要数字序列用 `range`。
2. **`range(1, 4)` 以为到 4**：含头不含尾，实际是 1,2,3。
3. **遍历时修改列表**：`for m in messages: messages.remove(m)` 是经典 bug，应遍历副本 `for m in messages[:]` 或用推导式重建。
4. **推导式过度嵌套**：超过一层 for + 一个 if 就改回普通循环，可读性优先。

## 常见面试问题
- 列表推导式和 for 循环哪个快？→ 推导式略快且更 Pythonic，但可读性优先。
- `enumerate` 的作用？→ 同时拿下标和元素，避免手动 `i += 1`。

## 练习
1. 遍历一个 list of dict 的消息历史，带序号打印。
2. 写 3 次重试循环，随机成功则 break。
3. 用推导式从消息历史提取 assistant 的所有回复。

[下一课：09-function →](09-function.md)
