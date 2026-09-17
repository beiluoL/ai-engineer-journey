# Project 01 — Python AI CLI Assistant

> 一个从 v0.1 逐步升级到 v1.0 的命令行 AI Assistant。
> 通过构建它，掌握 AI 开发真正需要的 Python 基础。

## 项目目标

通过持续升级一个 CLI AI Assistant，学习 Python 基础和 AI API 调用基础。

## 为什么从这个项目开始

AI 项目的代码全是 Python 写的。不理解 Python，就看不懂、写不出、改不动 AI 代码。
但 Python 内容太多——标准库、Web 框架、数据处理……一个有经验的 Java / 前端开发者
不需要从零学完整 Python 教程，而是直接从 AI 项目切入，**项目缺什么能力就学什么**。

这个项目让你跳过"Python 大全"，直接构建一个能真正调用 LLM 的 CLI 工具。

## 项目最终能力

完成后你会得到一个：

- 命令行交互的 AI Assistant
- 多轮对话 + 消息历史
- 可配置 API Key
- 有异常处理和测试
- 真正调用 LLM API

## 项目演进

```
v0.1  Variables (程序能存储和打印数据)
  ↓
v0.2  List / Dict / JSON / Messages (AI 项目最常见的数据结构)
  ↓
v0.3  Condition / Loop (程序有逻辑分支)
  ↓
v0.4  Function (代码可复用)
  ↓
v0.5  Module / Package (项目有结构)
  ↓
v0.6  Class / OOP (数据 + 行为结合)
  ↓
v0.7  Exception (程序能处理错误)
  ↓
v0.8  Persistence (程序能读写文件)
  ↓
v0.9  Environment / Dependencies (项目可独立管理)
  ↓
v0.10 HTTP / API (程序能和外部通信)
  ↓
v1.0  Real LLM (项目接入真实 AI)
```

## Milestones

| # | Milestone | 状态 | 核心能力 |
|---|-----------|------|----------|
| 01 | [Python Basics](milestones/01-python-basics.md) | ✅ | 变量 / 5 种基础类型 / type() / input() / print() / f-string |
| 02 | [Data and Messages](milestones/02-data-and-messages.md) | ✅ | List / Dict 嵌套 / JSON 序列化 / AI messages 数据结构 |
| 03 | [Control Flow](milestones/03-control-flow.md) | ⬜ | if / for / while / break / continue |
| 04 | [Functions](milestones/04-functions.md) | ⬜ | def / 参数 / 返回值 / 作用域 |
| 05 | [Modules and Packages](milestones/05-modules-and-packages.md) | ⬜ | import / 包结构 / __init__.py |
| 06 | [Classes and OOP](milestones/06-classes-and-oop.md) | ⬜ | class / self / 构造函数 / 继承 |
| 07 | [Exceptions](milestones/07-exceptions.md) | ⬜ | try / except / raise / 自定义异常 |
| 08 | [Persistence](milestones/08-persistence.md) | ⬜ | 文件读写 / JSON 文件 / 持久化消息 |
| 09 | [Environment and Deps](milestones/09-environment-and-deps.md) | ⬜ | venv / pip / requirements.txt |
| 10 | [HTTP API](milestones/10-http-api.md) | ⬜ | requests / HTTP 基础 / REST API |
| 11 | [Real LLM API](milestones/11-real-llm-api.md) | ⬜ | 真实 LLM 调用 / 串起所有知识 |
| 12 | [Async](milestones/12-async.md) | ⬜ | async / await / 并发基础 |
| 13 | [Typing and Dataclass](milestones/13-typing-and-dataclass.md) | ⬜ | 类型提示 / dataclass |
| 14 | [Config and Env](milestones/14-config-and-env.md) | ⬜ | .env / 配置管理 |
| 15 | [Testing and Debugging](milestones/15-testing-and-debugging.md) | ⬜ | pytest / 调试方法 |

## 当前状态

```
完成：
✅ Milestone 01 — Python Basics
✅ Milestone 02 — Data and Messages

进行中：
🔄 项目代码已有真实 LLM API 骨架

下一步：
⬜ Milestone 03 — Control Flow
⬜ Milestone 04 — Functions
...
⬜ Milestone 11 — Real LLM API（串起所有知识）
```

## 当前代码结构

```
src/
├── main.py               # 入口，已实现真实 API 调用骨架
├── .env.example          # API Key 模板
├── assistant/
│   ├── __init__.py
│   ├── client.py         # LLM 客户端
│   ├── config.py         # 配置
│   └── errors.py         # 自定义异常
└── tests/
    └── test_all.py
```

运行：

```bash
cd src/
cp .env.example .env   # 填入真实 API Key
python3 main.py
```

## 学到的核心能力

**当前已掌握：**
- Python 变量、5 种基础类型、type()、input()、print()、f-string
- List / Dict 嵌套、JSON 序列化、AI messages 数据结构
- 真实 LLM API 调用骨架

**最终会掌握：**
- 完整 Python 基础（变量 → OOP → 异常 → 文件 → 网络 → 异步 → 测试）
- AI 项目特有的数据结构（messages、JSON 处理）
- CLI 项目的完整工程结构

## 下一步

完成 Milestone 03-11，让项目从 v0.1 升级到 v1.0 真正可用的 AI CLI。

然后进入 [Project 02 — AI Assistant Service](../02-ai-assistant/)。
