# Project 02 — Engineering AI Assistant

## 项目目标

在 Project 01 的基础上，把 CLI Assistant 从 Python Script 工程化为真正的 Python Application。

## 为什么做这个项目

Project 01 证明了 Python 能调用 LLM，但代码还是脚本级的：没有虚拟环境、没有测试、没有异步、没有类型提示、没有 FastAPI。这些问题不解决，项目无法继续扩展。

## 解决什么问题

- 脚本级代码无法维护、无法协作、无法部署
- 同步 HTTP 无法处理高并发 AI 请求
- 没有类型提示，项目一大就容易出错
- 没有日志和测试，改了代码不知道会不会坏

## 最终能力

```
Python Script
    ↓
Python Application
    ↓
可维护 AI 服务
```

## 技术栈

- `asyncio` / `aiohttp` 或 `httpx`（异步 HTTP）
- `typing` / `dataclasses`（类型安全）
- `logging`（标准日志）
- `pytest`（测试）
- `FastAPI`（Web 框架）
- `uvicorn`（ASGI Server）

## 项目演进

```
Python AI CLI Assistant（v1.0，同步脚本）
  ↓ v0.1 — async / await
Python AI CLI（异步版）
  ↓ v0.2 — 类型提示 + dataclass
  ↓ v0.3 — config / logging
  ↓ v0.4 — packaging
  ↓ v0.5 — FastAPI 服务
Engineering AI Assistant Service
```

## Milestones

| # | Milestone | 状态 | 核心能力 |
|---|-----------|------|----------|
| 00 | Classes and OOP | 📝 | class / self / 构造函数 / 继承 / 封装 |
| 01 | Async / Await | 📝 | asyncio / coroutine / event loop |
| 02 | Async HTTP Client | ⬜ | aiohttp / httpx / 异步请求 |
| 03 | Type Hints | 📝 | typing / 泛型 / 函数签名 |
| 04 | Dataclass | 📝 | dataclass / pydantic model |
| 05 | Config / Environment | 📝 | .env / python-dotenv / 配置管理 |
| 06 | Logging | ⬜ | logging / 日志级别 / 结构化日志 |
| 07 | Testing / Debugging | 📝 | pytest / 单元测试 / 调试方法 |
| 08 | Packaging | ⬜ | pyproject.toml / 发布 / 安装 |
| 09 | FastAPI | ⬜ | FastAPI / 路由 / 中间件 / 依赖注入 |

## 当前状态

📝 部分成文（草稿待校对）：6 / 10 个 Milestone 已有内容，缺 02 / 06 / 08 / 09。
`src/` 仍是空的 —— 文档先行，代码尚未开始。

已成文文件（均为 📝 草稿，未人工校对）：
- `00-classes-and-oop.md`（原 Project 01 OOP 内容）
- `01-async-await.md`（原 Project 01 async 内容）
- `03-type-hints.md`（原 Project 01 typing 内容）
- `04-dataclass.md`（原 Project 01 dataclass 内容）
- `05-config-and-environment.md`（原 Project 01 config 内容）
- `07-testing-and-debugging.md`（原 Project 01 testing 内容）

## 当前版本

还未开始。

## 项目结构

```
src/
├── ...（继承自 Project 01）
└── ...（新增工程化代码）
```

## 已掌握能力

- Project 01 的所有 Python 基础
- 真实 LLM API 调用骨架

## 下一步

完成 Project 01 的 v1.0，让 CLI 真正可用。
然后开始 Project 02 的工程化升级。

**前置项目**：[Project 01 — Python AI CLI Assistant](../01-python-ai-cli/)
