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
| 03 | Embedding | 查表 Embedding + 正弦位置编码 + combine | ✅ 已落地 |
| 04 | Attention | `softmax(QKᵀ/√d_k)V` 手写 + 因果掩码 | ✅ 已落地 |
| 05 | Multi-Head Attention | 分头 / 拼接 / 输出线性映射 | ✅ 已落地 |
| 06 | Transformer Block | Pre-LN + 残差 + FFN | ✅ 已落地 |
| 07 | Decoder Stacking | 因果掩码 + N 层堆叠 + 输出投影 | ✅ 已落地 |
| 08 | Dataset / DataLoader | 滑窗采样、batch 与 pad、mask | ✅ 已落地 |
| 09 | Training Loop | 从零 autograd 反传 + 交叉熵 + 优化器 | ✅ 已落地 |
| 10 | Inference / Sampling | greedy / temperature / top-k 生成 | ✅ 已落地 |

拆分顺序 = 数据流动的方向（Tokenizer → Embedding → Block → Training → Inference），
理由与整张依赖图见 [Milestone 01](milestones/01-project-architecture.md)。

## 当前状态

**v1.0 —— 10/10 Milestone 全部落地：`src/tokenizer/`（M01-M02）+ `src/model/`（M03-M10，含从零 autograd），150 项 pytest 全绿（51 分词器 + 99 模型），9 个真实可跑 demo（demo_01 + demo_03~10），配图 11 张手写 SVG + 10 张真实终端截图。**

## 怎么跑起来

```bash
cd projects/06-mini-transformer-llm

# 1. 建虚拟环境
python3 -m venv .venv
.venv/bin/pip install -q pytest numpy

# 2. 跑测试（150 passed：51 分词器 + 99 模型，含梯度校验）
.venv/bin/python -m pytest -q

# 3. 跑 demo（输出同时打到终端和 demos/out/demo_XX_*.txt）
.venv/bin/python demos/demo_01_tokenizer.py     # M02 Tokenizer
.venv/bin/python demos/demo_03_embedding.py     # M03 Embedding
.venv/bin/python demos/demo_04_attention.py     # M04 Attention
.venv/bin/python demos/demo_05_multihead.py     # M05 Multi-Head
.venv/bin/python demos/demo_06_block.py         # M06 Transformer Block
.venv/bin/python demos/demo_07_decoder.py       # M07 Decoder Stack
.venv/bin/python demos/demo_08_dataloader.py    # M08 Dataset / DataLoader
.venv/bin/python demos/demo_09_training.py      # M09 Training Loop（loss 下降 + 梯度校验）
.venv/bin/python demos/demo_10_inference.py     # M10 Inference / Sampling
```

## 真实运行结果（v1.0）

**Tokenizer（M01-M02）**
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

**Model（M03-M10，纯 numpy / 无 torch）**
```
Embedding      W_e (500, 16)；正弦位置编码 pe[0,0]=0.0 / pe[0,1]=1.0（sin/cos 校验通过）
Attention      因果掩码上三角=-inf，第 0 行只能看自己，各行 softmax 和为 1
Multi-Head     4 头切分后各自行和为 1，输出 (seq, d_model)
Transformer    整机 logits (seq, 500)；Pre-LN + 残差
Training       玩具模型 150 步，loss 6.2100 → 4.7472（≈ log(500)=6.21 起，降 1.46）
GradientCheck  手写 autograd 对有限差分最大相对误差 2.60e-05（≪ 1e-3，反向全对）
Inference      贪心生成 15 token 全在词表内；temperature / top-k 采样输出为真实 token
```

## 项目结构

```
projects/06-mini-transformer-llm/
├── README.md                     # 本文件（10 个 milestone 勾选表）
├── pyproject.toml                # src/ 布局，pytest pythonpath=["src"]
├── src/
│   ├── tokenizer/                # M01-M02
│   │   ├── base.py               # Tokenizer 抽象 + 特殊 token 常量
│   │   ├── char_tokenizer.py     # 字符级分词器（基线）
│   │   ├── bpe.py                # 从零实现的 BPE 训练循环
│   │   └── sample_corpus.py      # 离线中英混排语料
│   └── model/                    # M03-M10（纯 numpy，无 torch）
│       ├── autograd.py           # 从零自动微分：Tensor / Parameter / Module / grad_check
│       ├── embedding.py          # TokenEmbedding + PositionalEncoding + combine
│       ├── attention.py           # scaled_dot_product_attention + causal_mask
│       ├── multihead.py           # MultiHeadAttention
│       ├── block.py               # TransformerBlock（Pre-LN + 残差 + FFN）
│       ├── decoder.py             # DecoderStack / TransformerLM
│       ├── dataloader.py          # 滑窗采样 + batch + pad + mask
│       ├── training.py            # SGD / Adam / Trainer（mask 交叉熵）
│       ├── inference.py           # generate（greedy / temperature / top-k）
│       └── __init__.py
├── tests/
│   ├── conftest.py               # 仓库内临时目录 fixture（不用 tmp_path）
│   ├── test_char_tokenizer.py    # 24 项
│   ├── test_bpe.py               # 27 项
│   └── test_model.py             # 99 项（含梯度校验 / 训练下降 / 生成）
├── demos/
│   ├── demo_01_tokenizer.py      # M02
│   ├── demo_03_embedding.py … demo_10_inference.py   # M03-M10（8 个）
│   ├── _demo_common.py           # _Tee 双写助手
│   └── out/demo_0X_*.txt         # 真实输出（文档里的数字都来自这里）
├── assets/                       # 手写 SVG（架构图 / BPE 循环 / 词表增长曲线 / 各层图）+ 真实终端截图
└── milestones/
    ├── 01-project-architecture.md … 10-inference-sampling.md   # 10 篇
```

## 已掌握能力

- Project 01-05 的所有能力
- 字符级与 BPE 两种分词器的实现与取舍（往返一致性、特殊 token、压缩率权衡）
- 从零手写 Transformer 全链路：Embedding + 正弦位置编码、`softmax(QKᵀ/√d_k)V` 与因果掩码、Multi-Head 切分/拼接、Pre-LN Transformer Block、Decoder 堆叠、滑窗 DataLoader
- **从零自动微分**：`Tensor` 拓扑排序 + 链式求导、广播梯度 `_unbroadcast`、中心差分 `grad_check` 验证反向正确（最大相对误差 2.60e-05）
- 训练闭环：前向 → mask 交叉熵 → `backward()` → 优化器 step，玩具模型 150 步 loss `6.21→4.75`
- 自回归生成：greedy / temperature / top-k 三种采样策略

## 下一步

Project 06 已收官（v1.0）。下一个项目是
[Project 07 — Open Source LLM](../07-open-source-llm/)：
接触真实开源模型生态，在本地跑通 Hugging Face 模型（本项目手写版跑通后，正好对照它"原来也是这么做的"）。

**前置项目**：[Project 05 — Research Agent / MCP Assistant](../05-agent-mcp/)
