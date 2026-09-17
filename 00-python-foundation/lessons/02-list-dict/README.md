# Lesson 02 — Python 数据结构：List / Dict 与 AI Messages

> Phase 0 / Python Foundation / Lesson 02
> 状态：[~] 即将学习

## 本章学什么

```text
list
dict
嵌套结构
list + dict
JSON
API 请求数据
AI messages
system
user
assistant
```

## 知识路线

```text
list
 ↓
dict
 ↓
nested data
 ↓
JSON
 ↓
HTTP Request
 ↓
LLM API
 ↓
messages
```

## 为什么学这个

LLM API 的核心数据结构就是 `messages`：

```python
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
```

这里同时用到了：

```text
list   → 外层方括号
dict   → 每条消息是一个字典
嵌套   → list 里装 dict
```

这一课学完，你就能看懂一次 LLM API 调用的请求体长什么样。

## 文件

| 文件 | 说明 |
|------|------|
| [lesson.md](lesson.md) | 课程教学（大纲，待学习时完善） |
| [demo.py](demo.py) | 最小可运行 Demo |

## 前置知识

- [Lesson 01 — 变量、类型与输入输出](../01-variables/)

## 服务于项目

- [Project 01](../../projects/01-python-ai-assistant/) v0.2：用 list / dict 管理消息

## 下一章

[Lesson 03 — 条件与循环](../03-condition-loop/)
