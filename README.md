# AI Engineer Journey

> Project-based journey from software developer to AI Engineer.

## 项目定位

面向有 Java / 前端基础、但 Python 和 AI 基础薄弱的开发者，通过项目驱动方式，
从 Python 基础一路学到 AI 应用、大模型、RAG、Agent、PyTorch、Transformer、
微调、评估、量化、部署，并最终能够自己实现和训练简化版语言模型。

## 学习目标

- **Python**：独立开发 Python 项目，看懂 AI 项目代码
- **AI 应用**：LLM API、Prompt、Tool Calling、RAG、Agent
- **模型工程**：Token / Embedding / Attention / Transformer / PyTorch
- **微调**：SFT / LoRA / QLoRA，理解微调流程
- **部署**：vLLM / Docker / 前后端联调
- **造模型**：亲手实现 TinyGPT

## 适合谁

```text
Java / 前端 / 后端开发者（Python 零基础）
    ↓
Python → Python Engineering → AI Application → LLM
    ↓
RAG → Agent → PyTorch → Transformer
    ↓
Fine-tuning → Evaluation → Inference → Deployment
    ↓
自己实现 TinyGPT
```

## 核心学习方式

1. **项目驱动**：每个知识点都落在真实项目上
2. **Java → Python 对照**：用已会的概念搭桥，明确机制差异
3. **复杂度自然增长**：script → function → module → package → app → AI service
4. **主动回忆**：不假装学会，每课都有主动回忆题

## 学习路线

```text
Phase 0  Python Foundation
Phase 1  Python Engineering
Phase 2  AI Application
Phase 3  Embedding & RAG
Phase 4  Agent / Tool Calling / MCP
Phase 5  PyTorch
Phase 6  Transformer / LLM
Phase 7  Hugging Face / 开源模型
Phase 8  Fine-tuning
Phase 9  Evaluation / Quantization
Phase 10 Inference / vLLM
Phase 11 Docker / Deployment
Phase 12 Mini LLM
Phase 13 Capstone
```

详见 [ROADMAP.md](ROADMAP.md)。

## 项目路线

14 个逐步升级的项目，从 Python CLI 到 TinyGPT。详见 [projects/](projects/)。

## 仓库结构

```text
ai-engineer-journey/
│
├── curriculum/     # 正式课程内容（唯一事实源）
├── labs/           # 单点技术实验
├── projects/       # 完整可运行项目
├── assessments/    # 能力验证
├── knowledge/      # 知识关系与索引
├── progress/       # 学习状态追踪
├── publishing/     # 对外发布内容
├── docs/           # 学习与维护规范
│
├── README.md
├── ROADMAP.md
├── PROGRESS.md
├── KNOWLEDGE-MAP.md
└── .gitignore
```

## 当前进度

Phase 0 — Python Foundation

```text
✅ Lesson 01 — Variables, Types and I/O
🔄 Lesson 02 — List / Dict, JSON and AI Messages
⬜ Lesson 03 — Condition / Loop
```

详见 [PROGRESS.md](PROGRESS.md)。

## 如何开始

```bash
# 1. 确认 Python 版本
python3 --version

# 2. 读第一课
open curriculum/00-python-foundation/01-variables/README.md

# 3. 跑 Demo
python3 curriculum/00-python-foundation/01-variables/demo/main.py
```

## 安全约定

- API Key 只通过环境变量 / `.env` 提供，`.env` 永不入库
- 仓库内只有 `.env.example` 模板

## 双远程同步

GitHub（origin）+ Gitee（gitee），每次提交双推。

## License

[MIT](LICENSE)
