# AI Engineer Journey

> Project-first journey from software developer to AI Engineer.

## 项目定位

面向有 Java / 前端基础、但 Python 和 AI 基础薄弱的开发者，
通过**连续项目**逐步构建 AI Engineer 能力。

**不是课程。不是知识库。是一组持续演进、可以运行、可以展示的工程项目。**

## 核心学习方式

```text
项目遇到问题
        ↓
学习必要知识
        ↓
知识进入代码
        ↓
运行 / 验证 / 调试
        ↓
项目升级
        ↓
形成可迁移能力
        ↓
进入下一个更复杂项目
```

## Project First 原则

```
Project > Milestone > Knowledge > Code > Practice > Documentation
```

## 学习路线（10 个项目）

| # | 项目 | 核心能力 | 状态 |
|---|------|----------|------|
| 01 | [Python AI CLI](projects/01-python-ai-cli/) | Python 基础 + AI API 调用 | 🔄 |
| 02 | [AI Assistant Service](projects/02-ai-assistant/) | Python Engineering + FastAPI | ⬜ |
| 03 | [AI Chat Web](projects/03-ai-application/) | Prompt / Streaming / Function Calling | ⬜ |
| 04 | [Personal RAG](projects/04-rag/) | Embedding / Chunk / Vector DB / RAG | ⬜ |
| 05 | [Research Agent](projects/05-agent-mcp/) | Agent / Tool / MCP Protocol | ⬜ |
| 06 | [Mini Transformer](projects/06-pytorch-transformer/) | PyTorch / Attention / Transformer | ⬜ |
| 07 | [Local Open Source LLM](projects/07-open-source-llm/) | Hugging Face / Tokenizer / 本地推理 | ⬜ |
| 08 | [Fine-tuning](projects/08-fine-tuning/) | SFT / LoRA / QLoRA | ⬜ |
| 09 | [Evaluation & Inference](projects/09-evaluation-inference/) | 评估 / 量化 / vLLM 服务化 | ⬜ |
| 10 | [TinyGPT Capstone](projects/10-mini-llm-capstone/) | 从零实现小型 LLM | ⬜ |

## 仓库结构

```text
ai-engineer-journey/
│
├── README.md              # 本文件
├── ROADMAP.md             # 路线图（接下来要构建哪些项目）
├── PROGRESS.md            # 当前状态
├── KNOWLEDGE-MAP.md       # 能力关系网（只展示关联，不复制正文）
├── LICENSE
├── .gitignore
│
├── projects/              # 核心内容（唯一事实源）
│   ├── 01-python-ai-cli/
│   │   ├── README.md          # 项目主页
│   │   ├── milestones/       # 学习里程碑（知识 + 问题 + 实现）
│   │   └── src/              # 项目代码
│   ├── 02-ai-assistant/
│   └── ...
│
└── publishing/            # 对外发布内容（输出层，不是知识源）
    ├── articles/
    ├── videos/
    └── diagrams/
```

## 单一事实源

所有知识只维护在 `projects/*/milestones/` 中。
其他目录只做引用、关联或派生输出。

## 如何开始

```bash
# 1. 克隆
git clone <repo> && cd ai-engineer-journey

# 2. 读第一个项目主页
open projects/01-python-ai-cli/README.md

# 3. 跑项目
cd projects/01-python-ai-cli/src
cp .env.example .env   # 填入 API Key
python3 main.py

# 4. 学 Milestone
open projects/01-python-ai-cli/milestones/01-python-basics.md
```

## 安全约定

- API Key 只通过环境变量 / `.env` 提供
- `.env` 永不入库，仓库只有 `.env.example`

## 双远程

GitHub（origin）+ Gitee（gitee），每次提交双推。

## License

[MIT](LICENSE)
