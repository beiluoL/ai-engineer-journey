# Project 06 — Mini Transformer / LLM

## 项目目标

从 AI 应用层进入模型内部，从零构建 Mini Transformer Decoder。

## 为什么做这个项目

会调用 LLM 不等同于理解 LLM。Project 01–05 我做的是「怎么把模型用好」——
CLI、RAG、Agent、工具调用，模型始终是黑盒。作为 AI 工程师，必须知道
Transformer 内部发生了什么，才能在它出问题时定位到是哪一层。

## 解决什么问题

- 只会"调 API"，看不懂模型内部代码
- 不理解 Attention【注意力机制】到底做了什么
- 不知道怎么从零写一个 Transformer Decoder

## 最终能力

```text
数据
    ↓
Token
    ↓
Embedding
    ↓
Attention
    ↓
Transformer
    ↓
Training
    ↓
Inference
```

自己解释和实现核心链路。

## 技术栈

核心实现用**纯 Python 标准库**（numpy 允许但不必需），不引入 torch：

- `from collections import Counter` —— BPE 的 pair 频次统计
- `abc.ABC` —— Tokenizer 契约抽象
- `json` —— 词表 / merges 落盘

**为什么故意不用 PyTorch**：`nn.MultiheadAttention` 一行能跑通的东西，不可能让我
理解 Attention。这一版要的是 `softmax(QKᵀ/√d_k)V` 真的被手写出来 —— 包括 mask
怎么加、维度怎么 reshape。代价是训不了真模型，只能训玩具规模；而玩具规模正好
能把每一步的中间结果打印出来看。等手写版能跑，再对照 PyTorch 就是「哦，它也是
这么做的」。

## Milestones

| # | Milestone | 核心能力 | 状态 |
|---|-----------|----------|------|
| 01 | Project Architecture | 五层拆分与输入输出契约 | ✅ 已落地 |
| 02 | Tokenizer | 字符级 / BPE 子词、特殊 token、往返一致性 | ✅ 已落地 |
| 03 | Embedding | 查表 Embedding + 位置编码 | ⬜ 未开始 |
| 04 | Attention | `softmax(QKᵀ/√d_k)V` 手写实现 | ⬜ 未开始 |
| 05 | Multi-Head Attention | 分头 / 拼接 / 线性映射 | ⬜ 未开始 |
| 06 | Transformer Block | 残差 + LayerNorm + FFN | ⬜ 未开始 |
| 07 | Decoder Stacking | 因果掩码 + N 层堆叠 | ⬜ 未开始 |
| 08 | Dataset / DataLoader | 滑窗采样、batch 与 pad | ⬜ 未开始 |
| 09 | Training Loop | 自回归 + 交叉熵 + 优化器 | ⬜ 未开始 |
| 10 | Inference / Sampling | greedy / temperature / top-k | ⬜ 未开始 |

拆分顺序 = 数据流动的方向（Tokenizer → Embedding → Block → Training → Inference），
理由与整张依赖图见 [Milestone 01](milestones/01-project-architecture.md)。

## 当前状态

**v0.1 —— 架构 + Tokenizer 已落地，51 项测试全绿，1 个真实可跑 demo。**

## 怎么跑起来

```bash
cd projects/06-mini-transformer-llm

# 1. 建虚拟环境
python3 -m venv .venv
.venv/bin/pip install -q pytest numpy

# 2. 跑测试（51 passed）
.venv/bin/python -m pytest -q

# 3. 跑 demo（输出同时打到终端和 demos/out/demo_01_tokenizer.txt）
.venv/bin/python demos/demo_01_tokenizer.py
```

## 真实运行结果（v0.1）

```
语料            1224 字符 / 295 个唯一字符 / 25 行（手写，不联网下载）
字符级词表      vocab_size = 299（4 个特殊 token + 295 个字符）
BPE 词表        vocab_size = 500（基础 299 + 201 次合并）
中英混排样本    Transformer 是一种神经网络架构，它在 2017 年被提出。
  字符级        35 个 token
  BPE           20 个 token：['Transformer', ' ', '是', '一种', '神', '经', '网络', ...]
整份语料        1224 → 705 token，压缩率 1.74×
中文合并        48 条：一个 / 模型 / 训练 / 词表 / 注意力 / 分词器 / 网络 ...
```

## 项目结构

```
projects/06-mini-transformer-llm/
├── README.md                     # 本文件（10 个 milestone 勾选表）
├── pyproject.toml                # src/ 布局，pytest pythonpath=["src"]
├── src/tokenizer/
│   ├── base.py                   # Tokenizer 抽象 + 特殊 token 常量
│   ├── char_tokenizer.py         # 字符级分词器（基线）
│   ├── bpe.py                    # 从零实现的 BPE 训练循环
│   └── sample_corpus.py          # 离线中英混排语料
├── tests/
│   ├── conftest.py               # 仓库内临时目录 fixture（不用 tmp_path）
│   ├── test_char_tokenizer.py    # 24 项
│   └── test_bpe.py               # 27 项
├── demos/
│   ├── demo_01_tokenizer.py      # 真实可跑
│   └── out/demo_01_tokenizer.txt # 真实输出（文档里的数字都来自这里）
├── assets/                       # 手写 SVG（架构图 / BPE 循环 / 词表增长曲线）+ 真实终端截图（pytest / demo）
└── milestones/
    ├── 01-project-architecture.md
    └── 02-tokenizer.md
```

Milestone 03 及之后的目录（`src/model/`、`src/training/`）现在**故意不存在** ——
空目录占位是最容易自欺的一种「已完成」。

## 已掌握能力

- Project 01-05 的所有能力
- 字符级与 BPE 两种分词器的实现与取舍（往返一致性、特殊 token、压缩率权衡）

## 下一步

Milestone 03 —— Embedding：用 Tokenizer 产出的 id 去查 `(V, d_model)` 的嵌入矩阵，
并加上位置编码。Tokenizer 决定了 `V` 是 500，Embedding 那层就得建 500 行。

**前置项目**：[Project 05 — Research Agent / MCP Assistant](../05-agent-mcp/)
