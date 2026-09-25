# Project 02 — 总纲：从 Python Script 到 Python Application

> 本篇是 Project 02 的**总纲**：讲清楚「为什么要工程化」以及 10 个 Milestone 的完整路线。
> 具体每一章的知识点在各 `milestones/NN-*.md` 里，代码在 `src/`。
> 从 `00-classes-and-oop.md` 中拆出（原文件混装了总纲与 Chapter 01）。

---


## 一、项目定位

上一阶段：

> Project 01 — Python AI CLI Assistant

我们已经完成：

```text
Python 基础
↓
数据结构
↓
控制流
↓
函数
↓
模块
↓
异常
↓
持久化
↓
虚拟环境
↓
HTTP API
↓
真实 LLM API
```

现在进入：

> **Project 02 — Python Engineering【Python 工程化】**

核心任务：

> **把一个“能运行的 AI CLI 程序”，升级成“真正的 Python AI 工程”。**

---

## 二、为什么需要这个项目

Project 01 可以运行，但继续开发后会遇到新的问题：

```text
请求一多
↓
程序被阻塞

代码一复杂
↓
类型越来越混乱

配置一多
↓
环境难以管理

程序一出问题
↓
不知道发生在哪里

功能越来越多
↓
修改一个地方可能影响其他地方

代码完成
↓
却不知道是不是正确
```

所以 Python Engineering 这一阶段，不再主要解决：

> “Python 语法怎么写？”

而是解决：

> **“Python 项目怎么工程化？”**

---

## 三、项目目标

最终把：

```text
Python CLI Script
```

升级成：

```text
Engineering AI Assistant
```

具备：

```text
异步能力
+
可靠 HTTP Client
+
类型系统
+
结构化数据
+
配置管理
+
日志
+
测试
+
Debugging【调试】
+
Packaging【打包】
+
FastAPI
```

最终架构：

```text
CLI / HTTP Request
        ↓
Application Layer
        ↓
AI Service
        ↓
Async HTTP Client
        ↓
LLM API
        ↓
Response
        ↓
Logging / Error Handling
        ↓
Response
```

---

## 四、Chapter / Milestone 正式路线

```text
Project 02
Engineering AI Assistant

Chapter 01
Async / Await【异步 / 等待】

Chapter 02
Async HTTP Client【异步 HTTP 客户端】

Chapter 03
Type Hints【类型提示】

Chapter 04
Dataclass【数据类】

Chapter 05
Config / Environment【配置 / 环境变量】

Chapter 06
Logging【日志】

Chapter 07
Testing / Debugging【测试 / 调试】

Chapter 08
Packaging【打包】

Chapter 09
FastAPI【Python Web 框架】

                ↓

Final Project
Engineering AI Assistant
```

---

## 五、项目演进关系

Project 01：

```text
用户
↓
CLI
↓
LLM API
↓
返回结果
```

Project 02：

```text
用户 / HTTP
↓
API Layer
↓
Application Service
↓
Async HTTP Client
↓
LLM API
↓
Response
↓
Logging
↓
Testing
↓
Service
```

联系描述：

Project 01 主要让程序“能调用模型”。

Project 02 开始解决真实工程中的并发、可维护性、配置、日志、测试和服务化问题。

因此 Project 02 并不是重新学一套 Python，而是在 **Project 01 的代码基础上持续重构**。

---
