# Project 08 — LoRA / QLoRA Fine-Tuning

## 项目目标

掌握模型微调，让通用模型变成领域模型。

## 为什么做这个项目

RAG 是外挂知识，Fine-tuning【微调】是把知识和行为"烧进"模型。生产中 LoRA / QLoRA 是标配。

## 解决什么问题

- RAG 能加知识但不能改变模型行为
- 需要模型在特定领域表现更好
- 需要让模型学会新的任务格式

## 最终能力

```text
Base Model
    ↓
Dataset
    ↓
Fine-Tuning
    ↓
LoRA / QLoRA
    ↓
Checkpoint
    ↓
Evaluation
    ↓
Usable Model
```

## 技术栈

- **纯 numpy 手写**：LoRA / NF4 量化 / QLoRA / 指令微调 / 断点续训 / Adapter 合并
- 不引入 torch、transformers、peft —— 每一行都是自己写的
- 基座模型复用 Project 06 手写的 Transformer 与其自动微分（`src/model/`）

## 项目演进

```
Local Open Source LLM
    ↓ SFT 基础
Fine-tuning v0.1
    ↓ LoRA / QLoRA
Fine-tuning v0.2
    ↓ Checkpoint + 评估
Fine-tuning v1.0   ✅
```

## Milestones

| # | Milestone | 核心能力 | 状态 |
|---|-----------|----------|------|
| 01 | Fine-Tuning | 微调概念 / SFT / 全量 vs LoRA 开销对比 | ✅ 已落地 |
| 02 | Dataset Preparation | Alpaca 指令数据 / 分词 / 长度分布 | ✅ 已落地 |
| 03 | Instruction Tuning | 指令格式 / 只在答案区算 loss | ✅ 已落地 |
| 04 | LoRA | 从零实现 `W + (α/r)·B·A`，B 零初始化 | ✅ 已落地 |
| 05 | QLoRA | NF4 分位量化 / 双量化 / 显存账本 | ✅ 已落地 |
| 06 | Training Configuration | rank / lr / alpha 真实扫描 | ✅ 已落地 |
| 07 | Checkpoint | Adapter 存取 / 断点续训 | ✅ 已落地 |
| 08 | Merge / Load Adapter | 合并回基座 / 等价性证明 | ✅ 已落地 |
| 09 | Fine-Tuned Model Evaluation | 域内困惑度 / 灾难性遗忘 | ✅ 已落地 |

## 当前状态

**v1.0 —— 9/9 Milestone 全部落地，189 项 pytest 全绿，9 个真实 demo，9 张真实终端截图 + 9 张手写架构图。**

主线叙事：**通用基座 → 冻结 → 注入 LoRA → Java 面试领域 SFT → 评估**。
领域数据集沿用 Project 07 手写的 `java_interview.json`（59 条，只读引用）。

### 关键实测数字

| 维度 | 实测结果 |
|---|---|
| 基座参数量 | 230,656（P06 的 `parameters()` 漏报 65,536 词嵌入，只报 165,120） |
| LoRA 可训练占比 | r=8 → 27,136 / 230,656 = **10.53%** |
| 训练显存 | LoRA 1.29 MB vs 全量 3.52 MB = **36.76%** |
| B 零初始化等价性 | 整机 262,144 个输出**逐位相同**，最大绝对误差 **0.000e+00** |
| 手写 autograd 对拍 | `grad_check` 最大相对误差 **6.585e-05** |
| 冻结是否生效 | 训练后基座被改动张量 **0 / 28**，adapter **26 / 26** |
| NF4 量化误差 | 相对误差 **0.0914**；比均匀 int4 低 **5.45%** |
| 压缩比 | fp32 → NF4+双量化 **7.75×**（0.5159 B/权重），双量化额外省 8.29% |
| 最优超参 | r=8 / alpha=16 / lr=0.01 → 域内困惑度 **405.7** |
| Adapter 体积 | 仅权重 115.76 KB vs 基座 901 KB（**7.8×**） |
| 合并等价性 | 合并前后最大绝对误差 **0.000e+00** |
| 领域微调效果 | 域内困惑度 **3649.9 → 421.1**（↓88.46%） |

### 三个"想当然被实测推翻"的结论

1. **"LoRA 更抗遗忘"在本项目不成立**：通用（见过）语料上 LoRA 涨 +240.71%，全量微调只涨 +118.83%。
   原因是基座本身欠训练，且 LoRA 等效 `mean|ΔW|/mean|W|` 已到 **104.1%**，并不"小改动"。
2. **小模型上 QLoRA 不划算**：adapter 106 KB 反而大于 NF4 量化后的基座 82.54 KB（**128.42%**）。
   量化收益随模型规模线性增长——7B 上才是 0.66 MB vs 3.5 GB 的区别（外推，非本机实测）。
3. **困惑度下降 ≠ 可用**：域内困惑度 3649.9 → 421.1 是真的，但玩具模型生成出来仍是乱码。
   指标是真的，能力不是。

### 顺带挖出的 P06 缺陷（本项目不改 P06，照实记录）

- `Module.parameters()` **漏掉整个词嵌入**（`TokenEmbedding` 未继承 `Module`），65,536 参数不在表内。
- `Adam` 动量从未累积：`step()` 里 m/v 是局部变量、没写回 `self.state`，训完非零元素 0/54,272。
- `Tensor._prev` 是 `set`，迭代顺序由对象地址决定 → 跨进程不可复现。本项目用 `enable_deterministic_autograd()` 在不改 P06 的前提下包一层修掉。

## 当前版本

v1.0

## 项目结构

```text
projects/08-fine-tuning/
├── README.md                  # 本文件
├── pyproject.toml             # pytest 配置（pythonpath=src）
├── src/ft/                    # 12 个手写模块
│   ├── paths.py               # 跨项目导入 P06 + 确定性自动微分开关
│   ├── base.py                # 基座模型构建 / 预训练 / npz 缓存
│   ├── lora.py                # LoRALinear：W + (α/r)·B·A
│   ├── inject.py              # 注入冻结基座 + 冻结/可训练参数分离
│   ├── quantize.py            # NF4 分位量化 + 双量化 + 反量化
│   ├── qlora.py               # QLoRALinear：NF4 基座 + LoRA 旁路
│   ├── sft_data.py            # Alpaca 指令数据 + 答案区 mask
│   ├── trainer.py             # 只训练 adapter 的训练器
│   ├── checkpoint.py          # adapter 存取 / 断点续训
│   ├── merge.py               # 合并回基座
│   └── eval.py                # 困惑度 / 遗忘 / 定性对比
├── tests/                     # 189 passed（lora 30 / quantize 25 / qlora 24 / ...）
├── demos/                     # 9 个真实可跑 demo（01-09 对应 9 个 Milestone）
│   └── out/*_terminal.txt     # 真实输出（文档里所有数字都来自这里）
├── assets/                    # 9 张真实终端截图 + 9 张手写架构图 SVG
├── milestones/                # 01-09 文档
└── models/                    # 基座与 adapter 缓存（.gitignore 排除，删掉可重建）
```

## 运行方式

```bash
# 跑测试（189 passed）
/Users/beiluo/.workbuddy/binaries/python/envs/default/bin/python -m pytest -q

# 跑任意一个 demo（输出同时打到终端和 demos/out/*.txt）
/Users/beiluo/.workbuddy/binaries/python/envs/default/bin/python demos/demo_04_lora.py
```

> 本项目刻意**不建 venv**：统一复用带 numpy 的托管解释器，省磁盘空间。

## 已掌握能力

- Project 01-07 的所有能力
- 从零手写 LoRA / NF4 量化 / QLoRA，并能用有限差分验证反向传播正确
- 指令微调的 mask 设计、超参扫描、断点续训、Adapter 合并与效果评估

## 下一步

Project 09 —— LLM Evaluation / Inference Platform（Benchmark / 量化部署 / vLLM）。

**前置项目**：[Project 07 — Open Source LLM](../07-open-source-llm/)
**底座来源**：[Project 06 — Mini Transformer / LLM](../06-mini-transformer-llm/)
