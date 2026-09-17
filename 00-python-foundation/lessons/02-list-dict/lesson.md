# Lesson 02：List / Dict → JSON → AI Messages

这一章非常关键，因为你会第一次看到：

> **Python 语法知识，为什么会直接决定你能不能写 AI 程序。**

今天的路线：

```text
list
 ↓
dict
 ↓
list + dict 嵌套
 ↓
JSON
 ↓
HTTP API
 ↓
LLM API
 ↓
messages
 ↓
system / user / assistant
```

---

# 1. 为什么先学 `list`？

上一章我们学习了：

```python
name = "Beiluo"
age = 29
```

这只能保存一个值。

但 AI 程序很快就会遇到：

> “我要保存多个东西。”

例如你学过的课程：

```python
skills = ["Java", "Python", "AI"]
```

这就是：

# List【列表】

Python：

```python
skills = ["Java", "Python", "AI"]

print(skills)
print(skills[0])
print(skills[1])
```

输出：

```text
['Java', 'Python', 'AI']
Java
Python
```

---

# 2. `list` 和 Java 的关系

可以先这样理解：

```text
Java
List<String>
   ↓
Python
list
```

Java：

```java
List<String> skills = Arrays.asList(
    "Java",
    "Python",
    "AI"
);
```

Python：

```python
skills = ["Java", "Python", "AI"]
```

Python 写起来更简洁。

---

# 3. List 最基本的操作

```python
skills = ["Java", "Python", "AI"]
```

## 取元素

```python
print(skills[0])
```

结果：

```text
Java
```

Python 的索引从：

```text
0
```

开始。

---

## 添加元素

```python
skills.append("RAG")
```

现在：

```python
print(skills)
```

得到：

```text
['Java', 'Python', 'AI', 'RAG']
```

---

## 修改元素

```python
skills[1] = "Python 3"
```

---

## 删除元素

```python
skills.remove("AI")
```

---

# 4. 一个非常重要的概念：List 是有顺序的

例如：

```python
skills = ["Java", "Python", "AI"]
```

这里：

```text
skills[0] = Java
skills[1] = Python
skills[2] = AI
```

顺序本身是数据的一部分。

这在 AI 中非常重要。

例如：

```python
messages = [
    "你好",
    "什么是 Python？",
    "谢谢"
]
```

消息顺序决定了：

> 谁先说、谁后说。

所以聊天历史非常自然地可以用 `list` 保存。

---

# 5. 但是 List 有一个问题

假设我们保存一条消息：

```python
message = ["user", "你好"]
```

你知道：

```text
message[0] = user
message[1] = 你好
```

但是这个结构不够清晰。

如果过几天再看到：

```python
message[0]
```

你还要记住：

> 0 是 role。

有没有更清楚的表示方式？

有。

---

# 6. Dict【字典】

Python：

```python
message = {
    "role": "user",
    "content": "你好"
}
```

这就是：

# Dict【字典】

Java 开发者可以先类比：

```text
Python dict
≈
Java Map
```

例如：

```java
Map<String, String> message = new HashMap<>();

message.put("role", "user");
message.put("content", "你好");
```

Python：

```python
message = {
    "role": "user",
    "content": "你好"
}
```

---

# 7. Dict 为什么特别适合 API？

因为数据有“名字”。

例如：

```python
message["role"]
```

得到：

```text
user
```

而：

```python
message["content"]
```

得到：

```text
你好
```

代码的可读性非常强。

---

# 8. List + Dict 组合

真正有意思的地方来了。

一条消息：

```python
message = {
    "role": "user",
    "content": "什么是 Python？"
}
```

多条消息：

```python
messages = [
    {
        "role": "system",
        "content": "你是一名 Python 老师"
    },
    {
        "role": "user",
        "content": "什么是 Python？"
    }
]
```

你现在应该开始看懂这个结构：

```text
messages
  ↓
list
  │
  ├── dict
  │   ├── role
  │   └── content
  │
  └── dict
      ├── role
      └── content
```

这就是：

> **List + Dict 嵌套结构。**

---

# 9. 这就是为什么 Python 数据结构对 AI 非常重要

以前你可能觉得：

> List、Map 不就是基础语法吗？

现在开始看到真实用途：

```text
Python List
    ↓
保存多条消息

Python Dict
    ↓
描述一条消息的结构

List + Dict
    ↓
描述整个对话
```

所以以后你看到：

```python
messages = [...]
```

首先应该想到：

> **这是一个 List，里面放着多个 Dict。**

---

# 10. 我们现在加入 JSON

JSON：

> **JavaScript Object Notation【JavaScript 对象表示法】**

它是一种非常常见的数据交换格式。

例如：

```json
{
  "role": "user",
  "content": "什么是 Python？"
}
```

它长得和 Python `dict` 非常像。

这也是 Python 做 Web / AI 开发非常舒服的原因之一。

---

# 11. Python Dict 与 JSON 很像，但不是同一个东西

这是一个必须记住的区别。

Python：

```python
message = {
    "role": "user",
    "content": "你好"
}
```

这是：

> Python `dict`【字典】

JSON：

```json
{
  "role": "user",
  "content": "你好"
}
```

这是：

> JSON 文本 / JSON 数据表示。

可以简单理解成：

```text
Python dict
   ↓
JSON 序列化
   ↓
字符串 / 字节
   ↓
HTTP
   ↓
服务器
```

---

# 12. Python 如何把 Dict 转成 JSON？

使用：

```python
import json
```

例如：

```python
message = {
    "role": "user",
    "content": "你好"
}

text = json.dumps(message, ensure_ascii=False)

print(text)
```

得到：

```text
{"role": "user", "content": "你好"}
```

这里：

```python
json.dumps()
```

可以理解为：

> **把 Python 对象序列化成 JSON 字符串。**

---

# 13. JSON 怎么转回 Python？

```python
data = json.loads(text)

print(data)
print(type(data))
```

结果：

```text
{'role': 'user', 'content': '你好'}
<class 'dict'>
```

所以：

```text
Python dict
    ↓
json.dumps()
    ↓
JSON

JSON
    ↓
json.loads()
    ↓
Python dict
```

这条转换链以后你会反复看到。

---

# 14. 现在进入真正的 AI

假设我们有：

```python
messages = [
    {
        "role": "system",
        "content": "你是一个 Python 老师"
    },
    {
        "role": "user",
        "content": "什么是 list？"
    }
]
```

为什么大模型 API 喜欢这样的结构？

因为模型需要知道：

```text
这句话是谁说的？
```

---

# 15. `system`

```python
{
    "role": "system",
    "content": "你是一个 Python 老师"
}
```

System Message：

> **系统消息【系统级指令/行为约束】**

主要用于提供模型的行为、角色和规则。

例如：

```text
你是 Python 教师
回答要适合初学者
代码使用 Python 3
先解释再给代码
```

---

# 16. `user`

```python
{
    "role": "user",
    "content": "什么是 list？"
}
```

User Message：

> **用户消息【用户输入】**

就是用户当前提出的问题或请求。

---

# 17. `assistant`

模型回答之后，可以表示成：

```python
{
    "role": "assistant",
    "content": "list 是 Python 中用于保存多个元素的数据结构。"
}
```

Assistant Message：

> **助手消息【模型输出】**

---

# 18. 完整对话

于是：

```python
messages = [
    {
        "role": "system",
        "content": "你是一名 Python 老师"
    },
    {
        "role": "user",
        "content": "什么是 list？"
    },
    {
        "role": "assistant",
        "content": "list 是 Python 中用于保存多个元素的数据结构。"
    },
    {
        "role": "user",
        "content": "它和 Java 的 List 一样吗？"
    }
]
```

你现在应该能读懂整个结构。

---

# 19. 这里第一次出现“上下文”

模型看到的不是：

```text
最后一句：
它和 Java 的 List 一样吗？
```

而是整个：

```text
system
+
user
+
assistant
+
user
```

这就是：

# Context【上下文】

所以你之前不理解的“模型为什么能记住上一句话”，现在可以从代码层面理解：

```text
历史消息
    ↓
messages list
    ↓
继续发送给模型
    ↓
模型获得上下文
```

不是 Python 在“魔法记忆”。

而是：

> **应用程序把历史上下文重新放进请求里。**

---

# 20. 把整条路线串起来

现在我们的联系描述：

用户首先产生一条消息，这条消息在 Python 中可以表示为一个 `dict`，其中 `role` 描述消息角色，`content` 保存文本内容。多条消息按照发生顺序放进 `list`，形成完整的 `messages`。这个 Python 数据结构可以转换成 JSON，并通过 HTTP 请求发送给 LLM API。模型收到 `system`、历史 `user`、历史 `assistant` 和当前 `user` 消息之后，就拥有了这次推理所需要的上下文。

所以：

```text
Python List
    ↓
保存多条消息

Python Dict
    ↓
描述一条消息

List + Dict
    ↓
messages

messages
    ↓
JSON

JSON
    ↓
HTTP Request

HTTP Request
    ↓
LLM API

LLM API
    ↓
Model Context
```

这条链非常重要。

---

# 21. Java 开发者对应关系

你可以先建立下面的映射：

|Python|Java|AI 中的作用|
|---|---|---|
|`list`|`List`|保存消息列表|
|`dict`|`Map`|描述单条消息|
|`str`|`String`|消息文本|
|`None`|`null`|空值|
|JSON|JSON|API 数据交换|
|`messages`|`List<Map<...>>`|对话上下文|

例如 Java：

```java
List<Map<String, String>> messages = new ArrayList<>();
```

Python：

```python
messages = []
```

然后：

```python
messages.append(
    {
        "role": "user",
        "content": "你好"
    }
)
```

这已经非常接近你以后实际写 LLM 应用的代码了。

---

# 22. 今天做第一个小实验

创建：

```text
00-python-foundation/
└── lessons/
    └── 02-list-dict/
        └── demo.py
```

先写：

```python
messages = [
    {
        "role": "system",
        "content": "你是一名 Python 老师"
    },
    {
        "role": "user",
        "content": "什么是 list？"
    }
]

print(messages)

print("\n第一条消息：")
print(messages[0])

print("\n第一条消息的角色：")
print(messages[0]["role"])

print("\n第二条消息的内容：")
print(messages[1]["content"])
```

你要亲自观察：

```text
messages
messages[0]
messages[0]["role"]
messages[1]["content"]
```

这是今天最重要的代码。

---

# 23. 再加入 JSON

继续：

```python
import json

json_text = json.dumps(
    messages,
    ensure_ascii=False,
    indent=2
)

print("\nJSON：")
print(json_text)
```

现在你就可以看到非常漂亮的：

```json
[
  {
    "role": "system",
    "content": "你是一名 Python 老师"
  },
  {
    "role": "user",
    "content": "什么是 list？"
  }
]
```

---

# 24. 一个你现在必须掌握的知识点

下面：

```python
messages[0]["role"]
```

实际上进行了两次访问：

```text
messages
 ↓
[0]
 ↓
第一个 dict
 ↓
["role"]
 ↓
"user"
```

所以：

```python
messages[0]["role"]
```

可以拆成：

```python
first_message = messages[0]

role = first_message["role"]
```

这就是 Python 处理嵌套数据的基本方式。

---

# 25. 再加一个循环

```python
for message in messages:
    print(message["role"], ":", message["content"])
```

结果：

```text
system : 你是一名 Python 老师
user : 什么是 list？
```

现在你又把上一章和这一章连接起来了：

```text
for
+
list
+
dict
```

这就是我们为什么采用“关联知识学习”，而不是把知识一个个割裂开。

---

# 26. 项目升级：AI CLI Assistant v0.2

现在开始让主线项目真正使用这些知识。

```text
Project 01
Python AI CLI Assistant

v0.1
输入 → 输出

      ↓

v0.2
messages

      ↓

保存：
system
user
assistant

      ↓

为后面的连续对话做准备
```

目前我们还不真正请求 LLM。

先建立：

```python
messages = [
    {
        "role": "system",
        "content": "你是一个 AI 学习助手"
    }
]

while True:
    user_input = input("You: ")

    if user_input == "/exit":
        break

    messages.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    print(messages)
```

现在你已经真正开始写：

> **AI 应用程序的数据层。**

下一步才是：

```text
messages
 ↓
LLM API
```

---

# 27. 今天的知识地图

```text
Python
│
├── list
│     ↓
│   多个元素
│
├── dict
│     ↓
│   key → value
│
├── list + dict
│     ↓
│   结构化数据
│
├── JSON
│     ↓
│   数据交换格式
│
└── AI API
      ↓
    messages
      │
      ├── system
      ├── user
      └── assistant
```

### 联系描述

`list` 负责保存有顺序的多个对象，`dict` 负责描述每个对象的字段。把两者组合以后，就可以自然表达聊天消息列表。这个数据结构能够被序列化成 JSON，通过 API 发送给模型；而 `system`、`user`、`assistant` 则进一步为每条消息附加角色信息，让模型知道上下文中每一句话来自哪里、承担什么作用。

---

# 28. 主动回忆：现在轮到你

不要重新看上面的解释，先凭自己的理解回答。

### Q1

下面：

```python
skills = ["Java", "Python", "AI"]
```

`skills` 是什么？

---

### Q2

下面：

```python
message = {
    "role": "user",
    "content": "你好"
}
```

`message` 是什么？

---

### Q3

下面：

```python
messages = [
    {"role": "system", "content": "你是老师"},
    {"role": "user", "content": "什么是 Python？"}
]
```

请说明：

```text
messages
messages[0]
messages[0]["role"]
messages[1]["content"]
```

分别是什么。

---

### Q4

为什么 AI API 不直接只传：

```text
"什么是 Python？"
```

而经常使用：

```python
messages = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
]
```

---

### Q5

你用自己的话解释：

> **Python `dict` 和 JSON 是不是同一个东西？**

---

### Q6：代码题

自己写：

```python
messages
```

要求包含：

```text
system：你是 Java + AI 老师
user：我正在学习 Python
assistant：很好，我们从基础开始
user：什么是 dict？
```

并使用 `for` 循环输出：

```text
system: ...
user: ...
assistant: ...
user: ...
```

---

这 6 题答完后，我们继续 **Lesson 02 的后半段：JSON + HTTP + 第一次真正调用 LLM API**。然后才进入 `if / for → function`，并让 **AI CLI Assistant v0.2 → v0.3** 真正跑起来。