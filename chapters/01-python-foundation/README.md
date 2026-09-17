# Chapter 01 — Python Foundation

## 本章目标

通过 AI 项目学习 AI 开发真正需要的 Python 基础。

## 项目

[Python AI CLI Assistant](project/python-ai-cli/)

## 为什么需要这一章

AI 项目的代码全是 Python 写的。不理解 Python，就看不懂、写不出、改不动 AI 代码。
这一章让项目从 v0.1 一个简单 echo，逐步升级到 v1.0 能真正调用 LLM API。

## 学习路线

1. Variables, Types and I/O — Python 最基本语法
2. List / Dict, JSON and AI Messages — AI 项目最常见的数据结构
3. Condition / Loop — 让程序有逻辑分支
4. Function — 把代码拆成可复用的块
5. Module / Package — 让项目有结构
6. Class / OOP — 让数据和行为结合
7. Exception — 让程序能处理错误
8. File / JSON — 让程序能读写数据
9. venv / pip — 让项目能独立管理依赖
10. HTTP / API — 让程序能和外部服务通信
10*. Real LLM API — 让项目接入真实 AI（把上面所有知识串起来）

## 项目演进

```
Before (v0.1)           After (v1.0)
┌──────────┐           ┌──────────────────┐
│ 简单 echo │           │ 真实 LLM CLI      │
│ 单轮对话  │  ──────► │ 多轮对话          │
│ 无历史    │           │ 消息历史          │
│ 无配置    │           │ API Key 配置     │
└──────────┘           │ 错误处理          │
                       └──────────────────┘
```

## 当前项目结构

```
project/python-ai-cli/
├── README.md
├── main.py               # 已实现真实 API 调用
├── .env.example
├── assistant/            # 包结构
│   ├── client.py         # LLM 客户端
│   ├── config.py         # 配置
│   └── errors.py         # 自定义异常
└── tests/
    └── test_all.py
```

## 已掌握能力

- Python 变量、5 种基础类型、type()、input()、print()、f-string
- List / Dict 嵌套、JSON 序列化、AI messages 数据结构

## 下一阶段

[Chapter 02 — Python Engineering](../02-python-engineering/)：让 CLI Assistant 工程化
