# AI Engineer Journey

> Project-based journey from software developer to AI Engineer.

## 项目定位

面向有 Java / 前端基础、但 Python 和 AI 基础薄弱的开发者，
通过项目驱动方式，从 Python 基础一路学到 AI 应用、大模型、RAG、Agent、
PyTorch、Transformer、微调、评估、量化、部署，并最终能够自己实现 TinyGPT。

## 核心学习方式

**项目驱动，章节就是项目升级过程。**

```text
项目需要这个能力
        ↓
学习必要概念
        ↓
修改项目
        ↓
验证
        ↓
继续升级项目
        ↓
最终形成 AI Engineer 能力
```

一个章节 = 一个学习阶段 + 一个持续演进的项目。

## 学习路线

```text
01 Python Foundation
02 Python Engineering
03 AI Application
04 RAG
05 Agent / Tool / MCP
06 PyTorch
07 Hugging Face
08 Transformer / LLM
09 Fine-tuning
10 Evaluation / Quantization
11 Inference
12 Deployment
13 Mini LLM
14 Capstone
```

## 项目路线（持续演进）

```text
Python AI CLI Assistant
v0.1 → v0.2 → v0.3 → ... → v1.0
      ↓
AI Assistant Service（Phase 2）
      ↓
AI Chat Web（Phase 3）
      ↓
Personal RAG（Phase 4）
      ↓
...
      ↓
Capstone 完整 AI 产品（Phase 14）
```

## 仓库结构

```text
ai-engineer-journey/
│
├── README.md              # 本文件
├── ROADMAP.md             # 路线图
├── PROGRESS.md            # 当前进度
├── KNOWLEDGE-MAP.md       # 全局知识网络
├── LICENSE
├── .gitignore
│
├── chapters/              # 核心内容（唯一事实源）
│   ├── 01-python-foundation/
│   │   ├── README.md        # 章节导航 + 项目目标
│   │   ├── 01-variables.md
│   │   ├── 02-list-dict-json.md
│   │   ├── ...
│   │   └── project/python-ai-cli/
│   ├── 02-python-engineering/
│   └── ...（共 14 章）
│
└── publishing/            # 对外发布内容（输出层，不是知识源）
    ├── README.md
    └── articles/
```

## 当前进度

Phase 01 — Python Foundation

```text
✅ 01-variables.md          完整
🔄 02-list-dict-json.md     完整
⬜ 03-condition-loop.md ~ 14-testing-debugging.md   占位
```

## 如何开始

```bash
# 1. 确认 Python
python3 --version

# 2. 读第一章
open chapters/01-python-foundation/README.md

# 3. 读 Lesson 01
open chapters/01-python-foundation/01-variables.md

# 4. 跑项目
cd chapters/01-python-foundation/project/python-ai-cli
python3 main.py
```

## 安全约定

- API Key 只通过环境变量 / `.env` 提供，`.env` 永不入库
- 仓库只有 `.env.example` 模板

## 双远程

GitHub（origin）+ Gitee（gitee），每次提交双推。

## License

[MIT](LICENSE)
