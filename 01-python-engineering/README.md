# 01-python-engineering — Phase 1：Python Engineering

> 把 Python 从「能跑」升级到「工程化」，为 AI 项目打下专业基础。

## 这一阶段学什么

- 虚拟环境与依赖管理（venv / pip / requirements.txt）
- 模块化与包结构设计
- 单元测试与日志规范
- async / await 异步编程
- 类型提示（typing）与 dataclass
- 项目结构与代码组织

## 为什么学

Phase 0 只是入门语法，真正写 AI 应用需要工程能力：依赖隔离、可测试、可维护、可异步并发。这阶段把 Python 从「脚本」升级为「工程」，是后续 FastAPI、RAG、Agent 的地基。

## 前置知识

- [Phase 0 — Python Foundation](../00-python-foundation/)

## 核心技能

- 用 venv 隔离项目依赖
- 拆分模块、写 __init__.py 组织包
- 用 pytest 写单元测试
- 用 logging 替代 print
- 用 async/await 处理并发
- 用 typing 写类型安全的函数

## 项目

| 项目 | 说明 |
|------|------|
| Project 01 升级 | 把 CLI 助手工程化重构 |
| Project 02 起步 | 为 AI Chat Web 搭建 Python 骨架 |

## 完成标准

- Project 01 完成工程化升级，有测试与日志
- 项目用 venv 管理，依赖可复现
- 能写 async 函数并解释事件循环
- 代码有类型提示，通过 mypy 检查

## 下一阶段

[Phase 2 — AI Application](../02-ai-application/)
