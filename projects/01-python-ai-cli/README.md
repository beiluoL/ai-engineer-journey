# Project 01 — Python AI CLI Assistant

> 输入问题 → 调用 LLM → 输出答案。这是整条 AI Engineer Journey 的第一个真实项目。

## 项目介绍

一个命令行 AI 助手。v0.1 实现最小核心：单轮问答。随着 Phase 0 课程推进，逐步升级出
连续对话、Streaming、历史保存、配置文件、错误处理、日志、测试，最终成为 v1.0 完整 CLI。

## 为什么做这个项目

学 Python 最快的路径不是背语法，而是立刻写一个"自己每天会用"的东西。
这个项目把 Phase 0 的 17 篇课程知识点全部落到真实代码上。

## 学习目标

- 把 Python 变量/dict/list/函数/类/异常/JSON/环境变量用于真实程序
- 看懂一次完整的 LLM API 调用链路（构造请求 → 发 HTTP → 解析 JSON）
- 建立"配置与代码分离、Key 永不进代码"的工程习惯

## 前置知识

- [00-python-foundation](../../00-python-foundation/README.md) 的 01~15 课
  （尤其 06-dict、09-function、11-class、12-exception、14-json、15-env）

## 技术栈

- Python 3.10+（仅标准库：urllib / json / dataclasses / unittest）—— v0.1 刻意零第三方依赖

## 项目结构

```text
01-python-ai-cli/
├── main.py               # 入口：读输入 → 调用 → 打印答案
├── assistant/
│   ├── __init__.py       # 包入口，统一导出
│   ├── config.py         # 配置加载（环境变量 + .env）
│   ├── errors.py         # 异常层级（LLMError → Auth/RateLimit/Response）
│   └── client.py         # LLMClient：构造请求 / 调用 API / 解析响应
├── tests/
│   └── test_all.py       # unittest 单元测试
├── .env.example          # 配置模板（真实 .env 永不提交）
└── README.md
```

## 快速开始

```bash
cd projects/01-python-ai-cli

# 1. 配置 Key（二选一）
export DEEPSEEK_API_KEY="sk-你的key"          # 方式一：环境变量
cp .env.example .env && $EDITOR .env          # 方式二：本地 .env

# 2. 运行
python main.py                     # 交互式
python main.py "用一句话解释 RAG"   # 命令行参数
```

## 核心原理：一次 LLM API 调用的完整链路

```text
用户问题 "什么是 RAG？"
        │
        ▼
main.py: input() 读取问题
        │
        ▼
config.py: 读取 DEEPSEEK_API_KEY（环境变量/.env，Key 永不写进代码）
        │
        ▼
client.build_payload(): 构造 JSON 请求体
        │   { "model": "deepseek-chat",
        │     "messages": [ {system 提示词}, {user: 问题} ],
        │     "stream": false }
        ▼
urllib: POST https://api.deepseek.com/chat/completions
        │   Header: Authorization: Bearer <API_KEY>
        ▼
API 返回 JSON 响应
        │   { "choices": [ { "message": { "content": "回答文本" } } ] }
        ▼
parse_answer(): 提取 content
        │
        ▼
main.py: print(答案)
```

任何错误（401 Key 无效 / 429 限流 / 网络失败 / JSON 异常）都会映射成对应的
`LLMError` 子类，main.py 统一捕获后给出人话提示。

## 学到了什么

- Python 类封装 HTTP 客户端；dataclass 管理配置
- dict ↔ JSON 互转（`dumps/loads`，`ensure_ascii=False`）
- 异常层级设计与错误状态码映射
- 环境变量管理密钥的安全实践

## 常见问题

- **Q: 为什么不用 requests / openai SDK？**
  v0.1 的目的就是看清 HTTP 调用的本质。Phase 1 引入第三方库时会逐一对比"框架替我们解决了什么"。
- **Q: 提示未找到 DEEPSEEK_API_KEY？**
  环境变量只对当前终端有效；或确认 `.env` 在运行目录下且变量名正确。
- **Q: 429 报错？**
  限流，稍等重试。v0.7 会加入自动重试。

## 下一步

- v0.2 连续对话（05-list：用 list 保存 message history）
- v0.3 Streaming（SSE 流式输出）
