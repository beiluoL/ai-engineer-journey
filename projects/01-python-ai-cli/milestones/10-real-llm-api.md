# Lesson 10 — Real LLM API：让 Python AI CLI Assistant 真正成为 AI Assistant

> 项目：Python AI CLI Assistant  
> 版本：v1.0  
> 核心主题：LLM【大语言模型】、LLM API【大模型接口】、API Key【接口密钥】、Model【模型】、Messages【消息列表】、System/User/Assistant、Request/Response、Token【词元】、Context【上下文】

---

# 一、这一章，我们终于要做什么？

前 9 章，我们一直在给这个项目修地基。

现在：

```text
v0.1
变量
 ↓
v0.2
List / Dict / JSON
 ↓
v0.3
控制流程
 ↓
v0.4
Function
 ↓
v0.5
Module
 ↓
v0.6
Exception
 ↓
v0.7
Persistence
 ↓
v0.8
Environment
 ↓
v0.9
HTTP / API
```

现在终于来到：

# v1.0 —— Real LLM API【真实大模型接口】

项目从：

```text
用户
 ↓
Python
 ↓
Mock Response【模拟响应】
```

升级成：

```text
用户
 ↓
Python AI CLI
 ↓
LLM API
 ↓
真实大语言模型
 ↓
AI Response
 ↓
Python
 ↓
用户
```

这意味着：

> **你的第一个真正 AI 应用诞生了。**

---

# 二、先不要急着写代码

这一章最重要的不是 SDK。

先回答：

> **大模型到底在哪里？**

你的电脑：

```text
Mac
 ↓
Python
 ↓
AI CLI Assistant
```

如果使用云端模型，那么模型实际上运行在：

```text
远程服务器
```

所以：

```text
你的 Mac
   │
   │ HTTP Request
   ↓
LLM API Server
   │
   │ Model Inference【模型推理】
   ↓
LLM
   │
   │ HTTP Response
   ↓
你的 Mac
```

你的 Python 程序本身：

> **不是大模型。**

它只是：

> **大模型的客户端。**

这个区别非常重要。

---

# 三、LLM 是什么？

LLM：

# Large Language Model【大语言模型】

简单理解：

> 能够处理和生成自然语言的大规模机器学习模型。

例如：

```text
用户：
什么是 HashMap？

LLM：
HashMap 是 Java 中基于哈希表实现的 Map...
```

但对于我们的 Python 程序来说：

我们暂时不需要研究：

```text
Transformer
Attention
Embedding
训练
反向传播
```

这些属于后面的：

```text
06-transformer-llm
```

当前先解决一个工程问题：

> **怎么调用已经训练好的模型？**

---

# 四、LLM API 是什么？

可以把：

```text
LLM
```

理解成：

```text
远程 AI 能力
```

把：

```text
LLM API
```

理解成：

```text
远程 AI 能力的程序化入口
```

例如：

```text
你的 Python
     ↓
LLM API
     ↓
模型
```

所以：

```text
API
=
程序访问模型能力的接口
```

---

# 五、为什么前面一定要学习 HTTP？

现在你会看到它们全部连接起来。

之前：

```text
Python
 ↓
httpx
 ↓
HTTP
 ↓
API
```

现在只是把 API 换成：

```text
LLM API
```

于是：

```text
Python
 ↓
httpx / SDK
 ↓
HTTP
 ↓
LLM API
 ↓
LLM
```

所以：

> LLM API 并没有推翻前面的 HTTP 知识。

恰恰相反：

> **它把前面的 HTTP 知识真正用起来了。**

---

# 六、第一件事情：API Key

访问很多云端 AI 服务时，需要：

# API Key【接口密钥】

它的作用可以简单理解为：

> **告诉 API 服务：“我是一个经过认证的调用方。”**

调用链：

```text
Python
 ↓
API Key
 ↓
LLM API
 ↓
认证
 ↓
允许调用
```

但要特别注意：

```text
API Key
≠
Model
```

API Key 是：

```text
身份 / 凭证
```

Model 是：

```text
你要调用的模型
```

---

# 七、API Key 千万不要写进代码

错误方式：

```python
API_KEY = "真实密钥"
```

更加不要：

```text
git add .
git commit
git push
```

把它上传到公开仓库。

正确方式：

```text
.env
```

例如：

```env
API_KEY=你的本地密钥
MODEL_NAME=你的模型名称
BASE_URL=你的服务地址
```

而：

```text
.env
```

已经在：

```text
.gitignore
```

中忽略。

---

# 八、配置层已经提前为今天做好准备

还记得 Lesson 08 的：

```text
config.py
```

现在终于有用了。

例如：

```python
import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
BASE_URL = os.getenv("BASE_URL")
```

现在：

```text
.env
 ↓
python-dotenv
 ↓
环境变量
 ↓
config.py
 ↓
LLM Client
```

整个设计已经形成闭环。

---

# 九、这一章为什么不强制你把真实 Key 发给我？

因为：

> **API Key 是秘密凭证。**

你应该只在自己的本地环境配置。

例如：

```env
API_KEY=真实密钥
```

而聊天里只展示：

```env
API_KEY=
```

或者：

```env
API_KEY=YOUR_API_KEY
```

永远不要把真实 Key 粘贴进聊天、代码仓库或截图。

---

# 十、Model【模型】又是什么？

假设一个 AI 平台提供多个模型：

```text
Model A
Model B
Model C
```

你调用 API 时需要告诉服务器：

> 我要哪个模型？

因此请求中通常会出现：

```json
{
  "model": "model-name"
}
```

所以：

```text
API Key
→ 我是谁

Model
→ 我要调用谁
```

这是非常重要的区分。

---

# 十一、最重要的数据结构：Messages

前面 Lesson 02 我们已经学习过：

```python
messages = [
    {
        "role": "user",
        "content": "你好"
    }
]
```

当时看起来只是：

> 一个 Python List。

现在你会发现：

> **它其实就是 LLM 对话 API 的核心数据结构之一。**

---

# 十二、为什么不是直接传一个字符串？

当然有些 API 可以：

```json
{
  "prompt": "你好"
}
```

但现代聊天模型接口经常使用：

```text
Messages【消息列表】
```

例如：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "你好"
    }
  ]
}
```

因为模型不仅需要知道：

```text
内容是什么
```

还需要知道：

```text
是谁说的
```

---

# 十三、Role【角色】

常见角色：

```text
system
user
assistant
```

---

## System【系统消息】

用于告诉模型：

> 你应该扮演什么角色、遵循什么规则。

例如：

```text
你是一名专业的 Java 教师。
回答问题时优先给出原理和实际案例。
```

---

## User【用户消息】

用户真正提出的问题。

例如：

```text
什么是 HashMap？
```

---

## Assistant【助手消息】

模型之前已经产生的回答。

例如：

```text
HashMap 是 Java 中的一种 Map 实现...
```

---

# 十四、为什么需要 Assistant 消息？

因为对话是连续的。

第一次：

```text
User：
什么是 HashMap？
```

模型：

```text
Assistant：
HashMap 是...
```

第二次：

```text
User：
那它为什么查询快？
```

如果模型只收到：

```text
那它为什么查询快？
```

它可能不知道：

> “它”到底指什么。

所以我们把历史一起发送：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "什么是 HashMap？"
    },
    {
      "role": "assistant",
      "content": "HashMap 是..."
    },
    {
      "role": "user",
      "content": "那它为什么查询快？"
    }
  ]
}
```

模型就获得了：

# Context【上下文】

---

# 十五、这里出现一个极其重要的认知

很多初学者会认为：

> “ChatGPT 记住了我刚才说的话。”

从 API 的角度看，更准确的理解通常是：

```text
你的程序
 ↓
保存历史消息
 ↓
下一次请求
 ↓
把相关历史消息重新发送给模型
 ↓
模型根据上下文生成回答
```

所以我们的：

```text
messages.json
```

现在开始变得非常重要。

---

# 十六、我们的项目终于闭环了

现在：

```text
用户输入
 ↓
messages
 ↓
保存历史
 ↓
调用 LLM
 ↓
Assistant Response
 ↓
加入 messages
 ↓
再次保存
```

也就是：

```text
Conversation State【对话状态】
```

开始真正参与 AI。

---

# 十七、先看真实 API 的抽象结构

不同厂商的 API 细节会不同。

但很多聊天接口在概念上类似：

```json
{
  "model": "model-name",
  "messages": [
    {
      "role": "system",
      "content": "你是一名 Python 教师。"
    },
    {
      "role": "user",
      "content": "什么是 List？"
    }
  ]
}
```

服务器返回类似：

```json
{
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "List 是一种..."
      }
    }
  ]
}
```

注意：

> 这里展示的是通用结构示意，不代表所有厂商的字段完全相同。

实际项目必须按照具体服务的 API 文档来构造请求和解析响应。

---

# 十八、为什么我们先理解原始 HTTP，再学习 SDK？

因为 SDK：

# SDK = Software Development Kit【软件开发工具包】

它通常帮你封装：

```text
HTTP
认证
JSON
Request
Response
异常
```

例如原始 HTTP：

```text
Python
 ↓
httpx
 ↓
HTTP POST
 ↓
JSON
 ↓
LLM API
```

使用 SDK 后：

```text
Python
 ↓
LLM SDK
 ↓
LLM API
```

看起来简单很多。

但如果你不懂底层：

> SDK 出问题时你就不知道问题发生在哪里。

---

# 十九、Java 开发者类比

你可以把：

```text
LLM SDK
```

类比成：

```text
Java SDK / Client
```

例如你调用某个远程服务：

```text
Java
 ↓
HTTP Client
 ↓
REST API
```

LLM 也是一样：

```text
Python
 ↓
LLM SDK / HTTP Client
 ↓
LLM API
```

所以不要把：

> “调用大模型”

想象成什么神秘操作。

本质上仍然是：

> **调用一个远程服务。**

---

# 二十、开始改造项目

现在：

```text
assistant.py
```

原来：

```python
def generate_mock_response(user_input):
    return f"我收到你的问题了：{user_input}"
```

我们要把：

```text
Mock Response
```

替换成：

```text
LLM Response
```

---

# 二十一、推荐的结构

项目：

```text
projects/01-python-ai-cli/
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── messages.json
│
└── src/
    └── ai_cli/
        ├── __init__.py
        ├── main.py
        ├── config.py
        ├── conversation.py
        ├── assistant.py
        ├── formatter.py
        ├── storage.py
        └── api_client.py
```

职责：

```text
main.py
    ↓
程序流程

assistant.py
    ↓
Assistant 业务逻辑

api_client.py
    ↓
LLM API 通信

config.py
    ↓
模型 / API Key / Base URL

conversation.py
    ↓
消息管理

storage.py
    ↓
持久化
```

---

# 二十二、API Client 的核心职责

`api_client.py` 不应该负责：

```text
命令解析
聊天历史
CLI UI
```

它只关心：

> **怎么调用 LLM API。**

可以先设计成：

```python
def chat(messages):
    ...
```

输入：

```python
messages
```

输出：

```python
assistant_content
```

这样 Assistant 层就不需要关心 HTTP 细节。

---

# 二十三、通用 API Client 结构

概念代码：

```python
import httpx

from .config import API_KEY, BASE_URL, MODEL_NAME


def chat(messages):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
    }

    response = httpx.post(
        BASE_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]
```

再次强调：

> 这里是为了学习“调用结构”。

不同 AI 服务的：

```text
BASE_URL
Authorization
请求字段
响应字段
```

可能不同。

实际接入时必须按照目标服务的官方 API 契约调整。

---

# 二十四、这段代码到底发生了什么？

第一步：

```python
headers = {
    "Authorization": f"Bearer {API_KEY}",
}
```

告诉服务：

> 我带着认证凭证来调用。

---

第二步：

```python
payload = {
    "model": MODEL_NAME,
    "messages": messages,
}
```

告诉服务：

> 我要调用这个模型，并把这组对话消息交给它。

---

第三步：

```python
httpx.post(...)
```

发送：

```text
HTTP POST
```

---

第四步：

```python
response.raise_for_status()
```

检查：

```text
HTTP 层是否成功
```

---

第五步：

```python
data = response.json()
```

把：

```text
JSON Response
```

转换为：

```text
Python Dict
```

---

第六步：

```python
data["choices"][0]["message"]["content"]
```

取出：

```text
Assistant 最终文本
```

---

# 二十五、这里一定要理解“解析响应”

很多初学者看到：

```python
data["choices"][0]["message"]["content"]
```

就开始死记。

不要死记。

应该理解成：

服务器返回：

```text
Response
 ↓
JSON
 ↓
Python Dict
 ↓
choices
 ↓
第一个结果
 ↓
message
 ↓
content
 ↓
模型生成的文本
```

所以：

```python
data["choices"][0]["message"]["content"]
```

只是：

> **沿着 JSON 数据结构把最终文本取出来。**

不同服务的响应结构可能不同。

---

# 二十六、assistant.py

现在：

```python
from .api_client import chat


def generate_response(messages):
    return chat(messages)
```

是不是比之前简单很多？

因为：

```text
assistant.py
```

不需要知道：

```text
HTTP
Header
POST
JSON
API Key
```

它只关心：

> 给我消息，我获得 Assistant 回答。

---

# 二十七、main.py 的核心流程

概念上：

```python
messages = load_messages()

while True:
    user_input = input("你：")

    if user_input == "/exit":
        save_messages(messages)
        break

    messages.append({
        "role": "user",
        "content": user_input,
    })

    assistant_content = generate_response(messages)

    messages.append({
        "role": "assistant",
        "content": assistant_content,
    })

    print(f"AI：{assistant_content}")

    save_messages(messages)
```

现在项目真正开始成为：

# AI Conversation Application【AI 对话应用】

---

# 二十八、完整运行链

用户：

```text
你好
```

↓

Python：

```python
{
    "role": "user",
    "content": "你好"
}
```

↓

加入：

```python
messages
```

↓

发送：

```text
HTTP POST
```

↓

LLM API：

```text
认证
 ↓
找到 Model
 ↓
处理 Messages
 ↓
模型推理
```

↓

返回：

```text
HTTP Response
```

↓

JSON：

```text
choices
 ↓
message
 ↓
content
```

↓

Python：

```text
assistant_content
```

↓

加入：

```python
messages
```

↓

保存：

```text
messages.json
```

↓

终端：

```text
AI：你好！有什么可以帮助你的？
```

---

# 二十九、联系描述：完整 AI 调用链

这是目前整个 Python 学习项目最重要的一条链：

```text
用户输入
   ↓
main.py
   ↓
Python Dict
   ↓
messages List
   ↓
assistant.py
   ↓
api_client.py
   ↓
构造 JSON Request
   ↓
HTTP POST
   ↓
LLM API Server
   ↓
API Key 认证
   ↓
选择 Model
   ↓
处理 Messages
   ↓
LLM 推理
   ↓
HTTP Response
   ↓
JSON Response
   ↓
Python Dict
   ↓
提取 Assistant Content
   ↓
assistant.py
   ↓
main.py
   ↓
messages
   ↓
messages.json
   ↓
用户
```

### 路线描述

用户输入首先进入 CLI 程序，被转换成一个带有 `role` 和 `content` 的 Python 字典，再加入整个 `messages` 列表。`assistant.py` 负责调用 AI 能力，而真正的网络通信由 `api_client.py` 完成。

`api_client.py` 把模型名称和消息列表构造成 JSON 请求，通过 HTTP POST 发送给 LLM API，同时通过 API Key 完成认证。

服务器收到请求后，根据指定的模型处理 Messages【消息列表】，执行模型推理，并通过 HTTP Response 返回 JSON 数据。

Python 程序解析 JSON，找到模型生成的 Assistant 消息，把它重新加入 `messages`。随后保存到 `messages.json`，这样下一轮请求就可以携带之前的对话历史。

因此：

> **`messages` 是对话状态，HTTP 是传输方式，LLM API 是模型能力入口，Model 是实际执行推理的模型。**

---

# 三十、为什么 messages.json 现在突然变得非常重要？

之前它只是：

```text
聊天记录文件
```

现在它开始承担：

```text
Conversation History【对话历史】
```

例如：

```json
[
  {
    "role": "user",
    "content": "什么是 JVM？"
  },
  {
    "role": "assistant",
    "content": "JVM 是 Java 虚拟机..."
  },
  {
    "role": "user",
    "content": "那 GC 呢？"
  }
]
```

下一次调用模型：

```text
messages
 ↓
LLM API
```

模型就能够利用之前的上下文。

---

# 三十一、这里第一次遇到 Token

现在可以开始认识：

# Token【词元】

不要把 Token 直接理解成：

> 一个汉字。

也不要理解成：

> 一个单词。

Token 是：

> **模型进行文本处理时使用的离散文本单元。**

具体怎么切分，由模型使用的 Tokenizer【分词器】决定。

例如：

```text
文本
 ↓
Tokenizer
 ↓
Tokens
 ↓
Token IDs
```

这个概念后面会详细学习。

现在只需要知道：

```text
用户输入越长
+
历史消息越多
        ↓
上下文中的 Token 越多
```

---

# 三十二、Context【上下文】是什么？

当前模型一次处理的：

```text
System
+
历史 User
+
历史 Assistant
+
当前 User
```

共同组成模型当前看到的上下文。

例如：

```text
System
 ↓
你是一名 Java 教师

User
 ↓
什么是 JVM？

Assistant
 ↓
JVM 是...

User
 ↓
那 GC 是什么？
```

这些内容一起构成：

# Context【上下文】

---

# 三十三、为什么上下文不能无限增长？

因为模型通常存在：

# Context Window【上下文窗口】

可以理解成：

> **一次请求中模型能够处理的上下文容量上限。**

因此：

```text
messages
越来越长
 ↓
Token 数量越来越多
 ↓
上下文越来越大
 ↓
可能达到 Context Window
```

以后你学习：

```text
RAG
Memory
Conversation Compression
Chunking
```

都会重新遇到这个问题。

---

# 三十四、现在先不要深入 Token

当前只建立：

```text
文本
 ↓
Tokenizer
 ↓
Token
 ↓
Model
```

后面的：

```text
Token ID
Embedding
Attention
Position
Transformer
```

会在后面的 LLM 基础章节系统展开。

不要在这里提前把整个 Transformer 学完。

---

# 三十五、Temperature 是什么？

真实 LLM API 里你可能看到：

```json
{
  "temperature": 0.7
}
```

# Temperature【温度】

它是影响模型生成过程随机性的一个参数。

粗略理解：

```text
较低
 ↓
输出倾向更加稳定

较高
 ↓
输出可能更加多样
```

但不要把：

```text
Temperature = “创造力”
```

当成严格定义。

它更准确地与：

> **生成时对概率分布进行调节**

有关。

这一章只需要知道它是一个：

# Generation Parameter【生成参数】

详细原理后面再讲。

---

# 三十六、Max Tokens

还可能看到：

```text
max_tokens
```

它通常用于限制：

> 模型生成内容的 Token 数量。

注意：

```text
输入 Token
```

和：

```text
输出 Token
```

不是完全一回事。

后面学习 Token / Context Window 时会详细拆。

---

# 三十七、第一版真实 LLM Client 的设计原则

现在先不要追求复杂。

我们的目标只有：

```text
chat(messages)
```

输入：

```python
messages
```

输出：

```python
assistant_content
```

于是：

```text
业务层
 ↓
chat(messages)
 ↓
API Client
 ↓
LLM API
```

这就是：

# Abstraction【抽象】

业务层不需要关心：

```text
HTTP 怎么发
Header 怎么写
JSON 怎么解析
```

---

# 三十八、异常处理必须保留

真实 API 和 Demo 最大的区别之一：

> **真实世界会失败。**

可能发生：

```text
API Key 错误
 ↓
401

权限问题
 ↓
403

请求过快
 ↓
429

服务器错误
 ↓
500

网络超时
 ↓
Timeout

网络连接失败
 ↓
RequestError
```

所以：

```python
try:
    ...
except ...
```

不能删除。

---

# 三十九、进一步思考：429 为什么特别重要？

429：

# Too Many Requests【请求过多】

例如：

```text
你的程序
 ↓
疯狂调用 API
 ↓
服务器限流
 ↓
429
```

以后学习 AI Agent【AI 智能体】时：

```text
Agent
 ↓
Tool
 ↓
LLM
 ↓
Tool
 ↓
LLM
 ↓
Tool
```

可能产生大量调用。

所以：

```text
Rate Limit【速率限制】
Retry【重试】
Backoff【退避】
```

都会成为重要的工程问题。

现在只需要认识它们。

---

# 四十、为什么不能无限 Retry？

假设：

```text
API
 ↓
429
 ↓
立即重试
 ↓
429
 ↓
立即重试
 ↓
429
```

可能变成：

```text
死循环
```

所以真正的生产系统通常需要：

```text
Retry
+
Backoff
+
Max Retry
```

后面的 AI 工程章节再详细实现。

---

# 四十一、现在你的项目第一次真正具备 AI 能力

以前：

```text
assistant.py
 ↓
字符串拼接
```

现在：

```text
assistant.py
 ↓
LLM API
 ↓
Model
 ↓
生成
```

这就是一个非常重要的边界：

```text
传统 Python CLI
        ↓
        ↓
        ↓
AI Application【AI 应用】
```

---

# 四十二、但是不要产生一个误解

现在项目：

```text
Python AI CLI Assistant
```

已经是：

> AI 应用。

但它还不是：

> AI Engineer 完整能力。

后面还有：

```text
LLM Fundamentals
Embedding
RAG
Agent
MCP
PyTorch
Transformer
Hugging Face
Fine-tuning
Evaluation
Quantization
Inference
Deployment
```

现在只是：

> **完成了第一次 LLM API 接入。**

---

# 四十三、Java + AI 的能力地图开始出现

现在你的知识网络已经可以画成：

```text
Python
 │
 ├── Web / HTTP
 │       ↓
 │     API
 │       ↓
 │     LLM API
 │       ↓
 │     LLM
 │
 ├── JSON
 │       ↓
 │    Messages
 │       ↓
 │    Context
 │
 └── Environment
         ↓
       API Key
```

这条路线未来继续扩展：

```text
LLM
 │
 ├── Token
 ├── Embedding
 ├── Context
 ├── Transformer
 │
 ├── RAG
 │    ├── Chunk
 │    ├── Embedding
 │    ├── Vector DB
 │    └── Rerank
 │
 └── Agent
      ├── Tool
      ├── Function Calling
      └── MCP
```

这就是你后面的 AI Engineer 知识网络。

---

# 四十四、主动回忆训练

现在先不要看标准答案。

## Q1

LLM 和 LLM API 是什么关系？

---

## Q2

API Key 和 Model 分别解决什么问题？

---

## Q3

为什么 API Key 不能直接写在 Python 源码里？

---

## Q4

为什么聊天模型通常需要 Messages，而不是只有一个字符串？

---

## Q5

System、User、Assistant 分别是什么？

---

## Q6

为什么下一轮用户问题需要携带历史消息？

---

## Q7

什么是 Context【上下文】？

---

## Q8

什么是 Context Window【上下文窗口】？

---

## Q9

`messages.json` 在现在的项目中有什么作用？

---

## Q10

下面这段代码：

```python
data["choices"][0]["message"]["content"]
```

为什么能够拿到模型回答？

---

## Q11

SDK 和直接使用 HTTP Client 有什么区别？

---

## Q12

为什么我们把 LLM 网络调用放到 `api_client.py`？

---

## Q13

如果 API 返回 401，首先应该从什么方向排查？

---

## Q14

如果 API 返回 429，意味着什么？

---

## Q15

完整讲一遍：

```text
用户输入
→
messages
→
HTTP
→
LLM
→
Response
→
Assistant
→
messages.json
```

---

# 四十五、面试标准话术

## 题目：你是怎么在 Python 项目中调用大模型的？

### 标准回答

> 我把大模型调用封装成独立的 API Client。用户输入首先会转换成带有 role 和 content 的消息对象，然后加入 messages 列表。API Client 根据配置读取模型名称、Base URL 和 API Key，构造 JSON 请求，通过 HTTP POST 调用 LLM API。收到响应后先检查 HTTP 状态，再解析 JSON，提取模型返回的 Assistant 内容，最后把 Assistant 消息加入对话历史并持久化。

---

## 题目：为什么使用 messages，而不是直接传字符串？

### 标准回答

> 因为聊天模型需要区分不同消息的角色和上下文。Messages 通常由 system、user、assistant 等不同 role 的消息组成，可以把系统指令、历史对话和当前用户问题组织在一起，让模型获得完整的上下文。

---

## 题目：API Key 为什么不能写在代码中？

### 标准回答

> API Key 属于敏感凭证，如果直接写在源码中，很容易被提交到 Git 仓库导致泄露。同时不同环境的凭证通常不同，所以更合理的方式是通过环境变量或者本地 `.env` 注入，代码只负责读取。

---

## 题目：SDK 和 HTTP API 有什么关系？

### 标准回答

> SDK 是对 API 调用过程的进一步封装。底层通常仍然涉及 HTTP 请求、认证、JSON 序列化和响应解析。使用 SDK 可以减少样板代码，但理解底层 HTTP API 有助于排查请求参数、认证、状态码和响应结构等问题。

---

# 四十六、项目挑战

现在给你的 AI CLI Assistant 增加：

```text
/system
```

命令。

例如：

```text
/system 你是一名严格的 Java 面试官
```

应该修改：

```python
{
    "role": "system",
    "content": "你是一名严格的 Java 面试官"
}
```

然后：

```text
用户：
什么是 HashMap？

AI：
...
```

模型应该按照新的 System 指令回答。

---

# 四十七、第二个挑战：显示当前上下文长度

增加：

```text
/stats
```

输出：

```text
消息数量：8
用户消息：4
AI 消息：3
System 消息：1
```

这一阶段先不要计算真正 Token。

先统计：

```python
len(messages)
```

以及不同 role 的数量。

以后进入 Token 章节，再把：

```text
消息数量
```

升级成：

```text
Token 数量
```

---

# 四十八、第三个挑战：限制历史消息

假设：

```text
messages
```

越来越长。

尝试增加：

```text
/history 10
```

只展示最近 10 条。

进一步：

```text
/chat-context 10
```

只把最近 10 条消息发送给模型。

这样你会第一次真正遇到：

# Context Management【上下文管理】

这会直接连接未来的：

```text
RAG
Memory
Context Compression
Long Context
```

---

# 四十九、v1.0 完成标准

完成下面这些才算真正完成：

```text
□ 我知道 LLM 是什么
□ 我知道 LLM API 是什么
□ 我知道 API Key 是什么
□ 我知道 Model 是什么
□ 我知道 Messages
□ 我知道 System / User / Assistant
□ 我理解为什么要携带历史消息
□ 我知道 Context
□ 我知道 Context Window
□ 我知道 HTTP 与 LLM API 的关系
□ 我知道 SDK 与 HTTP Client 的关系
□ 我能构造一个 LLM Request
□ 我能解析 LLM Response
□ 我知道 401
□ 我知道 403
□ 我知道 429
□ 我知道 Timeout
□ 我能解释 api_client.py 的职责
□ 我能完整讲出 LLM 调用链
```

---

# 五十、现在 Python AI CLI Assistant 已经完成第一阶段

```text
Python 基础
        ↓
Python 工程
        ↓
HTTP
        ↓
LLM API
        ↓
真实 AI Assistant
```

这意味着：

# 第一阶段正式完成

```text
Project 01 — Python AI CLI Assistant
```

已经从：

```text
Python 语法
```

走到了：

```text
Python AI Application
```

---

# 五十一、下一阶段开始：Python Engineering

接下来不能马上跳 Transformer。

先继续补齐真正 AI 工程开发需要的 Python 能力。

下一阶段路线：

```text
01-python-engineering
│
├── HTTP Client 深入
├── Async / Await【异步】
├── Type Hints【类型提示】
├── Dataclass【数据类】
├── Logging【日志】
├── Testing【测试】
├── Debugging【调试】
├── Project Packaging【项目打包】
└── FastAPI
```

然后：

```text
02-ai-application
```

开始：

```text
LLM Application
Prompt
Structured Output
Streaming
Function Calling
```

再进入：

```text
03-embedding-rag
```

正式学习：

```text
Embedding【嵌入】
Vector【向量】
Vector Database【向量数据库】
Chunk【文本块】
Retriever【检索器】
Rerank【重排序】
RAG
```

再之后：

```text
04-agent-tool-mcp
```

学习：

```text
Tool
Function Calling
Agent
MCP
```

最后才进入：

```text
PyTorch
 ↓
Transformer
 ↓
Hugging Face
 ↓
Fine-tuning
 ↓
Evaluation
 ↓
Quantization
 ↓
Inference
 ↓
Deployment
```

---

# 五十二、整个 AI Engineer Journey 的主线

到这里，你应该开始看到整个项目真正的主线：

```text
Python
  ↓
Python Engineering
  ↓
HTTP / API
  ↓
LLM API
  ↓
LLM Application
  ↓
Embedding
  ↓
RAG
  ↓
Agent
  ↓
MCP
  ↓
PyTorch
  ↓
Transformer
  ↓
Open Source LLM
  ↓
Fine-tuning
  ↓
Evaluation
  ↓
Quantization
  ↓
Inference
  ↓
Deployment
  ↓
Build Tiny LLM
```

### 路线描述

前半段解决“**我能不能写出 AI 应用**”。

中间解决“**我能不能让 AI 应用拥有知识、工具和复杂任务能力**”。

后半段解决“**我能不能真正理解、修改、微调、部署甚至自己实现模型**”。

因此现在不要急着跳到 Transformer。

你刚刚完成的是整个路线中非常关键的第一座桥：

> **从普通 Python 开发者 → 能够独立调用 LLM API 的 AI 应用开发者。**

下一步进入 **Python Engineering【Python 工程化】**，把异步、类型、日志、测试等真正补齐，然后再进入 LLM 应用工程。