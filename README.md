# AI Engineer Journey

> 面向有 Java / 前端基础、但 Python 和 AI 基础薄弱的开发者：
> 通过项目驱动的方式，从 Python 基础一路学到 AI 应用、大模型、RAG、Agent、PyTorch、
> Transformer、微调、评估、量化、vLLM、Docker 部署，最终能自己实现和训练简化版语言模型。

**一句话定位：从 Python 到 AI Engineer 的项目驱动学习路线。**

## 适合谁

```text
Java / 前端 / 后端开发者（Python 零基础）
    ↓
Python → Python 工程 → AI Application → LLM
    ↓
RAG → Agent → PyTorch → Transformer
    ↓
Fine-tuning → Evaluation / Quantization → Deployment
    ↓
独立开发 AI 产品、微调模型、部署模型、实现自己的 TinyGPT
```

## 核心架构

```text
Curriculum  — 核心学习内容（我应该学什么）
Labs        — 小实验验证（怎么验证这个知识）
Projects    — 完整可运行项目（怎么做成真正的软件）
Assessments — 能力验证（我到底会不会）
Knowledge   — 知识关系与索引（知识之间怎么连接）
Progress    — 学习状态追踪（我现在在哪里）
Publishing  — 对外发布内容（如何公开学习成果）
```

## 仓库结构

```text
ai-engineer-journey/
│
├── README.md                  # 本文件
├── ROADMAP.md                 # 总路线图
├── PROGRESS.md                # 当前进度
├── KNOWLEDGE-MAP.md           # 知识关系地图
│
├── curriculum/                # 核心课程（Phase 0 ~ 13）
│   └── 00-python-foundation/
│       ├── README.md
│       ├── 01-variables/
│       │   ├── README.md
│       │   ├── lesson.md
│       │   ├── demo/main.py
│       │   └── exercises/
│       ├── 02-list-dict/
│       └── ...
│
├── labs/                      # 小实验
├── projects/                  # 完整项目
│   └── 01-python-ai-cli/
├── assessments/               # 能力验证（quiz / coding / interview / benchmark）
├── knowledge/                 # 知识关系与索引
├── progress/                  # 学习状态
├── publishing/                # 对外内容（articles / videos / diagrams / social）
│
├── docs/                      # 学习与维护规范
└── mistakes/                  # 错题本
```

## 当前状态

Phase 0 — Python Foundation

```text
✅ Lesson 01 — Variables / Types / Input / Output
🔄 Lesson 02 — List / Dict / JSON / AI Messages
⬜ Lesson 03 — Condition / Loop
```

见 [PROGRESS.md](PROGRESS.md) 和 [progress/current.md](progress/current.md)。

## 快速开始

```bash
# 1. 确认 Python 版本
python3 --version

# 2. 读第一课
open curriculum/00-python-foundation/01-variables/README.md

# 3. 运行 Demo
python3 curriculum/00-python-foundation/01-variables/demo/main.py
```

## 学习原则

1. **Project-Based Learning**：每个知识点都落在真实项目上
2. **不允许知识跳跃**：严格按依赖顺序推进
3. **Java → Python 对照教学**：用已会的 Java 概念搭桥
4. **不假装学会**：讲解 → Demo → 练习 → 主动回忆 → 检查
5. **复杂度自然增长**：script → function → module → package → application → AI service

## 安全约定

- API Key 只通过环境变量 / `.env` 提供，`.env` 永不入库
- 仓库内只有 `.env.example` 模板，不含任何真实密钥

## 双远程同步

GitHub（origin）+ Gitee（gitee），每次提交双推。

## License

[MIT](LICENSE)
