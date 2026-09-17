# AI Engineer Journey

> 面向有编程基础（Java / 前端 / 后端）、但没有 Python 和 AI 大模型基础的开发者：
> 通过项目驱动的方式，从 Python 0 基础一路学到 AI 应用开发、RAG、Agent、PyTorch、
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

## 学习目标

- **Python**：独立开发 Python 项目（FastAPI / asyncio / Pydantic / 测试 / 调试）
- **AI 应用**：LLM API、Streaming、Prompt、Tool Calling、RAG、Agent、MCP
- **模型工程**：理解 Token / Embedding / Attention / Transformer，会用 PyTorch 与开源模型
- **微调**：数据准备、SFT、LoRA / QLoRA、评估、量化
- **部署**：GPU 推理、vLLM、Docker、前后端联调
- **造模型**：亲手实现简化版 Transformer 与 TinyGPT
- **工程判断力**：面对需求能判断该用 Prompt、RAG、Agent、微调还是训练

这不只是一个"教程仓库"，而是一套完整的学习系统：

```text
学习路线 + 课程 + 真实项目 + 实验代码 + 工程实践
+ 面试知识 + 技术文章素材 + 视频素材 + 个人作品集
```

---

## 核心原则

1. **Project-Based Learning**：每个知识点都落在真实项目上，不堆纯知识。
2. **不允许知识跳跃**：严格按依赖顺序推进（Python → 工程 → API → RAG → Agent → 深度学习 → 微调 → 部署）。
3. **Java → Python 对照教学**：用已会的 Java 概念搭桥，但明确指出机制差异。
4. **可理解 > 可运行 > 可验证 > 可维护 > 可扩展**。
5. **不假装学会**：代码生成 ≠ 掌握。每个阶段都有讲解 → Demo → 练习 → 我的答案 → 检查。

## 仓库结构

```text
ai-engineer-journey/
│
├── README.md              # 本文件
├── ROADMAP.md             # 总路线图（Phase 0 ~ 13）
├── PROGRESS.md            # 当前进度（每次学习后更新）
├── KNOWLEDGE-MAP.md       # 知识地图（节点依赖关系）
├── CONTRIBUTING.md        # 参与规范
│
├── 00-python-foundation/  # Phase 0：Python 基础
│   ├── lessons/           #   14 课
│   ├── exercises/         #   练习
│   └── projects/          #   Project 01：Python AI CLI Assistant
│
├── 01-python-engineering/ ~ 12-mini-llm/  # Phase 1~12
├── 13-capstone/           # Phase 13：毕业项目
│
├── content/               # 自媒体内容（articles / diagrams / scripts / video / social）
├── mistakes/              # 错题本（python / ai / llm / project）
├── exercises/             # 跨阶段练习
└── docs/                  # 术语表 / FAQ / 学习规则 / 开发规则
```

## 快速开始

```bash
# 1. 确认 Python 版本（建议 3.11+）
python3 --version

# 2. 进入 Project 01，阅读 README
cd projects/01-python-ai-assistant

# 3. 配置密钥（不要把真实 Key 写进代码或 git）
cp .env.example .env   # 然后编辑 .env 填入你的 DEEPSEEK_API_KEY

# 4. 运行
python main.py
```

## 当前状态

见 [PROGRESS.md](PROGRESS.md)。当前阶段：**Phase 0 — Python Foundation**，同步建设 **Project 01**。

同步维护于 GitHub 与 Gitee 两个仓库（origin = GitHub 主仓库，gitee = Gitee 镜像，每次提交双推）。

## 如何参与

欢迎 Issue / PR：勘误、补充练习、踩坑记录、文章素材。见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE)

## 安全约定

- API Key 只通过环境变量 / `.env` 提供，`.env` 永不入库（已在 `.gitignore` 中）。
- 仓库内只有 `.env.example` 模板，不含任何真实密钥。
