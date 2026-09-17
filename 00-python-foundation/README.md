# 00-python-foundation — Phase 0：Python Foundation

> 在真实 AI 项目中掌握 AI 开发所需要的 Python 基础。
> 不做传统 Python 教材，强调：Python 基础 + AI 开发场景 + Java 对照 + 实际项目。

## 这一阶段学什么

Python 的核心语法与数据结构，但每个知识点都对接到 AI 开发场景。
学完能独立写出 Python 脚本、看懂 LLM API 的请求结构、完成一个命令行 AI 助手。

## 为什么学

后面所有阶段（AI Application / RAG / Agent / PyTorch / 微调 / 部署）都建立在 Python 之上。
Phase 0 的目标不是"学完 Python 语法"，而是"能开始写 AI 项目"。

## 前置知识

- 会任一编程语言（Java / JavaScript / 前端 / 后端）
- 不需要 Python 基础

## 核心技能

```text
变量 / 类型 / input / output
 ↓
list / dict / JSON / AI messages
 ↓
条件 / 循环
 ↓
function
 ↓
module / package
 ↓
class / OOP
 ↓
exception
 ↓
file / json
 ↓
venv / pip
 ↓
http / api
 ↓
async
 ↓
typing / dataclass
 ↓
config / env
 ↓
testing / debugging
```

## 课程目录

| # | 课程 | 状态 |
|---|------|------|
| 01 | [variables — 变量、类型与输入输出](lessons/01-variables/) | [x] 已完成 |
| 02 | [list-dict — List / Dict / JSON / AI Messages](lessons/02-list-dict/) | [~] 即将学习 |
| 03 | [condition-loop — 条件与循环](lessons/03-condition-loop/) | [ ] |
| 04 | [function — 函数](lessons/04-function/) | [ ] |
| 05 | [module-package — 模块与包](lessons/05-module-package/) | [ ] |
| 06 | [class-oop — 类与面向对象](lessons/06-class-oop/) | [ ] |
| 07 | [exception — 异常处理](lessons/07-exception/) | [ ] |
| 08 | [file-json — 文件与 JSON](lessons/08-file-json/) | [ ] |
| 09 | [venv-pip — 虚拟环境与包管理](lessons/09-venv-pip/) | [ ] |
| 10 | [http-api — HTTP 与 API](lessons/10-http-api/) | [ ] |
| 11 | [async — 异步编程](lessons/11-async/) | [ ] |
| 12 | [typing-dataclass — 类型提示与 dataclass](lessons/12-typing-dataclass/) | [ ] |
| 13 | [config-env — 配置与环境变量](lessons/13-config-env/) | [ ] |
| 14 | [testing-debugging — 测试与调试](lessons/14-testing-debugging/) | [ ] |

## 课程与项目关系

每课学完都落地到 Project 01：

```text
Lesson 01 变量 / 类型 / input / output
 ↓ Project 01 v0.1 基础

Lesson 02 List / Dict / JSON / Messages
 ↓ Project 01 v0.2 消息结构

Lesson 03 if / for
 ↓ Project 01 v0.3 命令处理

Lesson 04 function
 ↓ Project 01 v0.4 函数封装

Lesson 05 module / package
 ↓ Project 01 v0.5 模块拆分

...
 ↓
Project 01 v1.0 完整 Python AI CLI Assistant
```

## 项目

| 项目 | 说明 |
|------|------|
| [01-python-ai-assistant](projects/01-python-ai-assistant/) | Python AI CLI Assistant（主线） |

## 练习

| 练习 | 对应课程 |
|------|----------|
| [01-variables](exercises/01-variables/) | Lesson 01 |
| [02-list-dict](exercises/02-list-dict/) | Lesson 02 |

## 完成标准

- 14 课全部完成，每课有 demo + 练习
- Project 01 升级到 v1.0：完整命令行 AI 助手
- 能看懂一次 LLM API 调用的请求 / 响应结构

## 下一阶段

[Phase 1 — Python Engineering](../01-python-engineering/)
