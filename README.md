# AI Engineer Journey

> **Project First — 通过连续项目逐步构建 AI Engineer 能力**

## 项目定位

面向有 Java / 前端基础、但 Python 和 AI 基础薄弱的开发者，
通过 **10 个连续项目**，从 Python 基础一路学到 AI Application、RAG、Agent、
PyTorch、Transformer、微调、评估、量化、部署，并最终自己实现 Tiny LLM。

**这不是课程，不是知识库，是一组持续演进、可以运行、可以展示、可以继续扩展的工程项目。**

## Project First 原则

```text
Project
  >
Milestone
  >
Knowledge
  >
Code
  >
Practice
  >
Documentation
```

**项目遇到问题 → 学习知识 → 知识进入代码 → 运行验证 → 形成能力 → 进入下一个项目**

## 10 个项目路线

| # | 项目 | 核心能力 | 状态 |
|---|------|----------|------|
| 01 | [Python AI CLI Assistant](projects/01-python-ai-cli/) | Python 基础 + 真实 LLM API | 🔄 |
| 02 | [Engineering AI Assistant](projects/02-engineering-ai-assistant/) | Python 工程化 + FastAPI | ✅ |
| 03 | [AI Application](projects/03-ai-application/) | Prompt / Streaming / Function Calling | ⬜ |
| 04 | [AI Knowledge Base / RAG](projects/04-rag/) | Embedding / Chunk / Vector DB / RAG | ⬜ |
| 05 | [Research Agent / MCP](projects/05-agent-mcp/) | Agent / Tool / MCP Protocol | ⬜ |
| 06 | [Mini Transformer / LLM](projects/06-mini-transformer-llm/) | PyTorch / Attention / Transformer | ⬜ |
| 07 | [Open Source LLM](projects/07-open-source-llm/) | Hugging Face / Tokenizer / 本地推理 | ⬜ |
| 08 | [LoRA / QLoRA Fine-Tuning](projects/08-fine-tuning/) | SFT / LoRA / QLoRA | ⬜ |
| 09 | [LLM Evaluation / Inference](projects/09-evaluation-inference/) | 评估 / 量化 / vLLM 服务化 | ⬜ |
| 10 | [Tiny LLM Capstone](projects/10-tiny-llm-capstone/) | 从零实现小型 LLM | ⬜ |

> 状态列指**内容状态**：✅ 已完成 / 🔄 进行中 / 📝 草稿 / ⬜ 未开始。
> 「我是否真的学会了」另记在 [PROGRESS.md](PROGRESS.md) 的学习进度轨 —— 文档就绪 ≠ 已掌握。

## 仓库结构

```text
ai-engineer-journey/
│
├── README.md              # 本文件
├── ROADMAP.md             # 10 项目路线图
├── PROGRESS.md            # 双轨进度（学习进度 / 内容生产）
├── KNOWLEDGE-MAP.md       # 能力关系网（只展示关联，不复制正文）
├── CONTRIBUTING.md        # 维护规范（单一事实源 / 命名 / 分级 / Git 约定）
├── LICENSE
├── .gitignore
│
├── mistakes/              # 错题本：真实踩过的坑（日期 + 原因 + 修复）
│   └── README.md
│
├── projects/              # 核心内容（唯一事实源）
│   ├── 01-python-ai-cli/
│   │   ├── README.md          # 项目主页（必须对齐规范模板）
│   │   ├── milestones/       # 学习里程碑（Project First 模板）
│   │   │   ├── 01-variables.md
│   │   │   ├── 02-list-dict-json.md
│   │   │   └── ...（共 10 个）
│   │   ├── exercises/        # 配套练习（01-basic 已有题，02/03/04 待播种）
│   │   └── src/              # 项目代码
│   ├── 02-engineering-ai-assistant/
│   └── ...（共 10 个项目）
│
└── publishing/            # 对外发布内容（输出层，不是知识源）
    ├── articles/          # 课程学习笔记型文章
    ├── tutorials/         # 独立成篇的图文教程（md + html + assets/）
    └── finetune-series/   # 微调系列草稿库（未校对，择优转正为 tutorials）
```

## 单一事实源

> 所有知识只维护在 `projects/*/milestones/` 中。其他目录只做引用、关联或派生输出。

禁止出现平行知识体系：`curriculum/`、`labs/`、`knowledge/`、`assessments/`、`progress/`。

## 技术术语规范

所有教学内容中的英文技术术语必须优先使用：**英文名称【主流中文名称】**

例如：Embedding【向量嵌入】、Token【词元】、Attention【注意力机制】、Fine-Tuning【微调】、Quantization【量化】

## 如何开始

```bash
# 1. 读第一个项目主页
open projects/01-python-ai-cli/README.md

# 2. 跑项目
cd projects/01-python-ai-cli/src
cp .env.example .env   # 填入真实 API Key
python3 main.py

# 3. 学 Milestone
open projects/01-python-ai-cli/milestones/01-variables.md
```

## 安全约定

- API Key 只通过环境变量 / `.env` 提供
- `.env` 永不入库，仓库只有 `.env.example`

## 双远程

GitHub（origin）+ Gitee（gitee），每次提交双推。

## License

[MIT](LICENSE)
