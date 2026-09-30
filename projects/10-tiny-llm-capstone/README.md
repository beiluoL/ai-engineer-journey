# Project 10 — Tiny LLM / AI Engineer Capstone

## 项目目标

把前面所有能力重新串起来，完成最终 AI Engineer Capstone【综合项目】——从零实现一个小型 LLM 工程。

## 为什么做这个项目

前面 9 个项目都是专项能力。这个项目把它们全部串起来：自己完整实现一个 LLM 从 Tokenizer → 训练 → 推理 → 部署的全链路，并且**每个数字都来自一次真实运行**。

## 解决什么问题

- 能不能从零实现一个完整的 LLM 工程？
- 能不能把前面学到的所有能力真正串起来（而不是十个互不相干的 demo）？
- 能不能作为 AI Engineer 独立交付完整项目？

## 最终能力

```text
Data
    ↓
Tokenizer
    ↓
Model
    ↓
Training
    ↓
Evaluation
    ↓
Inference
    ↓
Optimization
    ↓
Serving
    ↓
Application
```

## 技术栈

- **纯 numpy + Python 标准库手写**：BPE 分词器、Transformer Decoder、训练闭环、推理引擎、量化、HTTP 服务
- 不引入 torch / transformers / fastapi / vllm —— HTTP 服务直接用标准库 `http.server` + `urllib`
- **三层复用**前面项目的已验真能力：
  - **P06**（`06-mini-transformer-llm/src`）：手写 Tensor / autograd、`TransformerLM`、`BPETokenizer`/`CharTokenizer`
  - **P08**（`08-fine-tuning/src/ft`）：`enable_deterministic_autograd()`（把 `Tensor._prev` 从无序 `set` 改成有序 list）
  - **P09**（`09-evaluation-inference/src/ie`）：`metrics`（含 ECE 校准）、`quantize`、`kvbook`、`engine`、`serve`、`autoeval`、`compare`

## 项目演进

```
前面 9 个项目的所有能力
    ↓ 完整整合
Tiny LLM v0.1（Tokenizer + Model）
    ↓ Training + Evaluation
Tiny LLM v0.2
    ↓ Inference + Optimization + Serving
Tiny LLM v1.0   ✅
```

## Milestones

| # | Milestone | 核心能力 | 状态 |
|---|-----------|----------|------|
| 01 | Project Architecture | 唯一配置入口（`TinyConfig` + `validate()`）/ 八段流水线 | ✅ 已落地 |
| 02 | Tokenizer | BPE 手写 + **带归因的 roundtrip 报告** | ✅ 已落地 |
| 03 | Dataset | 清洗 / 切分 / **泄漏检查** / 滑动窗口打包 | ✅ 已落地 |
| 04 | Embedding | 查表 + 正弦位置编码（0 可训练参数）+ 参数占比 | ✅ 已落地 |
| 05 | Transformer Block | Pre-LN + 残差 + FFN + **因果性硬性自检** | ✅ 已落地 |
| 06 | Training | 调度 / 裁剪 / 早停回滚 / 断点续训 | ✅ 已落地 |
| 07 | Evaluation | 语言层 / 校准层 / 生成层 + **两组配对对照** | ✅ 已落地 |
| 08 | Inference | 采样四旋钮 / KV Cache 等价性 / **真·流式** | ✅ 已落地 |
| 09 | Optimization | 量化（INT8/INT4/NF4）+ KV Cache 显存账本 | ✅ 已落地 |
| 10 | Serving | OpenAI 兼容 HTTP + SSE + 冒烟 + 压测 | ✅ 已落地 |
| 11 | Complete System | 八段一条命令跑完，可缓存 / 可分段 / 报告可机读 | ✅ 已落地 |

## 当前状态

**v1.0 —— 11/11 Milestone 全部落地，71 项 pytest 全绿，11 个真实 demo，11 张真实终端截图 + 11 张手写架构图。**

主线叙事：**把"能不能跑通"变成"能不能证明它对"。**
从零到一的顺序：Tokenizer → Dataset → Embedding → Block → Training → Evaluation → Inference → Optimization → Serving → 一条命令串起来。

### 关键实测数字

| 维度 | 实测结果 |
|---|---|
| 语料 / 分词 | 295 行 / 10,651 字符 / 876 个不同字符；`bpe vocab=1280`（4 特殊 + 854 字符 + 422 合并），压缩 **1.445 字/token**（省 30.79%），UNK 率 **0.33%** |
| 分词 roundtrip | train **100.00%**；val **68.18%** 且 14/14 失败**全部归因于 OOV**、实现 bug **0** |
| 数据集 | train 251 行 / val 44 行，泄漏 `overlap=0`；打包后 train **206** / val **37** 样本 |
| Embedding | `(1280, 64)` 查找表 = **81,920** 参数（**35.6%**），与输出投影合计 **71.1%**；查表 vs `one-hot@W` 误差 **0.000e+00**；正弦 PE **0 可训练参数**、每位置范数恒为 **5.6569** |
| Transformer Block | 2 层 × 4 头 × d_model 64、d_ff=128；单 Block **33,216** 参数（attention 16,384 / FFN 16,576 / LN 256）——**注意力与 FFN 平手**（因为 `d_ff = 2·d_model`） |
| 因果性自检 | 过去位置误差 **0.000e+00**、未来位置误差 **1.191e+01**、确定性 **0.000e+00**，**三项全过**；掩码反例：logits 最大差 **0.6892** 但 argmax 同为 **676**（⇒ 必须比数值） |
| 训练 | train loss **7.1547 → 3.6882**、val **6.2283 → 5.7551（最优，第 800 步）→ 5.8234**；1200 步 ≈ **46.2 遍**；**早停触发并回滚到第 800 步**；1050/1200 步被裁剪，全程无 NaN |
| 确定性 | 检查点读回 **28/28** 张量误差 **0.000e+00**；跨进程重训 **0.000e+00**；断点续训 30 步 **0.000e+00** |
| 评估（三层） | PPL **315.79** / token_acc **0.1736**（相对随机下降 75.3%）；ECE **0.0662**、**4/5 箱过度自信**；生成层贪心 **16.84** / 采样 **31.81**，但**关键词覆盖 0.000** |
| 配对对照 | A（未训练 vs 已训练）**37 胜 0 负 0 平**、一致性 **1.000**；B（早停回滚 vs 不回滚）PPL **低 6.61%**、**24 胜 13 负 0 平** |
| 推理 | KV Cache 等价误差 **3.442e-15**、加速 **1.34×**；**TTFT 0.20 ms / 总耗时 4.73 ms**（修复假流式前是 4.25/5.60 ms）；同 seed 逐字复现 **True** |
| 量化 | **INT8 3.85× / ΔPPL +0.08%**、**INT4 7.42× / +2.66%**、**NF4 7.75× / +4.01%**；per-channel 让 INT8/INT4 的 MSE 降低 **48.1% / 47.4%**（NF4 为 0.0%） |
| KV 显存账本 | fp32 **1024 B/token**、fp16 **512 B/token**；`seq_len=64` 占权重 3.56%、`seq_len=4096` 占 **227.6%**；**1801 token 的 KV = 整个模型** |
| 服务化 | 冒烟四项全过（**200/200/200/400**）；并发 4 吞吐 **130.60 req/s**（**6/6 成功**）；平均 **8.14 ms** / P50 **5.41 ms** / **P95 22.88 ms** |
| 全链路 | 八段一条命令跑完，**有缓存 0.928 s**（冷启动真训约 26 s） |

### 最值得记住的三条

1. **过拟合是被量出来的，不是猜的。** train loss 7.1547 → 3.6882 看着很成功，但 val 在第 800 步触底后回升。**早停真正干的事不是"提前结束"，而是"结束并把权重退回到最好那一刻"** —— 只停不回滚，交出去的是 PPL 338.13 而不是 315.79。
2. **PPL 只是入场券，不是判决书。** 相对随机下降 75.3%（看着不错）与关键词覆盖 **0.000**（完全答不了题）**同时成立**。三层评估（语言 / 校准 / 生成）+ 配对显著性，缺一层结论就不成立。**这个 230K 参数的模型会拼词、不会答题——这里的价值是把这个真相量化出来，而不是让 loss 曲线替它遮羞。**
3. **优化必须同时报收益和代价。** 量化是**有损**（代价是 ΔPPL）、KV Cache 是**无损**（代价是显存）。只报压缩比、不报 ΔPPL 的方案不可信；而且**"INT4 基本无损"是小模型上的假命题**——实测 ΔPPL **+2.66%**，是 INT8（+0.08%）的 33 倍。

### 其他反直觉发现

- **"参数都在 FFN"不是规律，是 `d_ff/d_model = 4` 的后果。** 令 `2·d·d_ff = 4·d²` 得 `d_ff = 2d`；本项目 `d_ff = 2·d_model`，所以 FFN 与注意力**平手**（49.9% vs 49.3%）。
- **argmax 相等 ≠ 模型没被污染。** 去掉因果掩码后 logits 最大差 0.6892，但 argmax 依然是同一个 —— **只比"最终预测对不对"的测试，在掩码这类结构错误面前是盲的。**
- **"假流式"的现象是 TTFT == 总耗时。** 先算完整段再逐 token `yield`，用户感知不到任何流式好处。改成直接消费解码生成器后，TTFT 从 4.25 ms 降到 **0.20 ms**。
- **低温在欠训练模型上会退化成复读。** T=0 重复率 **0.887**、T=0.3 是 0.714 —— "降低温度提高质量"这个直觉，在本来就没学会的模型上是反的。
- **top_k 会降多样性，top_p 不会。** top_k=5 把 distinct-1 从 0.941 砍到 0.500（砍掉了长尾），top_p=0.9 保留 0.941。
- **MSE 最小 ≠ 端到端最优。** NF4 的 MSE 比 INT4 还低，但 ΔPPL 反而更高（+4.01% vs +2.66%）。
- **ECE 依赖分箱数，不是一个绝对量。** M07 演示用 5 箱得 0.0662、流水线默认 10 箱得 0.0709 —— **引用 ECE 必须带箱数，否则两个"都对"的数字看起来像矛盾。**
- **复用检查点必须选 `best` 而不是 `last`。** 选错会让全链路 PPL 变成 338.13，和 M06/M07 对不上 —— **跨章节的一致性取决于一个"选哪个检查点"的细节。**

## 当前版本

v1.0

## 项目结构

```text
projects/10-tiny-llm-capstone/
├── README.md                  # 本文件
├── pyproject.toml
├── data/
│   └── corpus.txt             # 领域语料（295 行 / 10,651 字符，问答题格式）
├── src/tiny/                  # 12 个手写模块
│   ├── paths.py               # 路径派生 + 跨项目 sys.path 挂载 + 确定性开关
│   ├── config.py              # 唯一配置入口 TinyConfig（8 个子配置 + validate）
│   ├── tok.py                 # BPE 分词器封装 + roundtrip 归因报告
│   ├── data.py                # 清洗 / 切分 / 泄漏检查 / 滑动窗口打包
│   ├── model.py               # 构建 + 参数账 + forward_sanity（因果/确定性自检）
│   ├── train.py               # 训练闭环（调度/裁剪/早停回滚/检查点）
│   ├── evaluate.py            # 三层评估 + 配对对照
│   ├── infer.py               # 采样四旋钮 + KV Cache + 真·流式
│   ├── optimize.py            # 量化收益代价 + KV 显存账本
│   ├── serve.py               # 服务封装 + 冒烟 + 压测
│   └── pipeline.py            # 八段流水线编排 + 产物缓存
├── tests/                     # 71 项 pytest 全绿
├── demos/                     # 11 个真实可跑 demo（01-11 对应 11 个 Milestone）
│   └── out/*_terminal.txt     # 真实输出（文档里所有数字都来自这里）
├── assets/                    # 11 张真实终端截图 + 11 张手写架构图 SVG
├── milestones/                # 01-11 文档
└── models/                    # 流水线产物（tokenizer.json / tiny_lm_best.npz / report.json）
```

## 运行方式

```bash
# 跑测试（71 passed）
/Users/beiluo/.workbuddy/binaries/python/envs/default/bin/python -m pytest -q

# 跑任意一个 demo（输出同时打到终端和 demos/out/*.txt）
/Users/beiluo/.workbuddy/binaries/python/envs/default/bin/python demos/demo_11_complete_system.py

# 一条命令跑完八段流水线
/Users/beiluo/.workbuddy/binaries/python/envs/default/bin/python -m tiny.pipeline
# 可选：--force（忽略缓存）/ --steps N / --only config,tokenizer / --no-serve
```

> 本项目刻意**不建 venv**：统一复用带 numpy 的托管解释器，省磁盘空间。

## 已掌握能力

- Project 01-09 的所有能力
- 从零串起一条 LLM 全链路：手写 BPE 分词（含归因）、防泄漏数据集、Transformer Decoder、训练闭环（早停回滚 + 断点续训）
- **把"验证"当成一等公民**：因果性自检、确定性对拍、KV Cache 等价性、量化 ΔPPL、断言 argmax 之外的数值
- 三层评估（语言 / 校准 / 生成）+ 配对显著性，把"模型到底能不能用"量成数字
- 手写采样策略、KV Cache、量化（INT8/INT4/NF4）与显存账本
- 用标准库起 OpenAI 兼容服务（SSE 流式 + 冒烟 + 并发压测 + 分位延迟）
- 交付一条**可缓存、可分段重跑、报告可机读**的 ML 流水线

## 下一步

Project 10 已完成。后续可扩展方向：

1. 把 `include_general=True` 的通用语料进一步扩充，观察生成层关键词覆盖能否从 0.000 提起（这是一个可量化的探索）
2. 用 P07 的模型加载/量化线在 Colab GPU 上把同一套评估流程跑一遍，对比 CPU 版的小模型结论是否仍然成立
3. 把 `pipeline.py` 接进 CI：报告可机读 ⇒ 可以直接做"超参改动 → PPL 变化"的自动回归

**前置项目**：[Project 09 — LLM Evaluation / Inference Platform](../09-evaluation-inference/)
**底座来源**：[Project 06 — Mini Transformer / LLM](../06-mini-transformer-llm/) · [Project 08 — LoRA / QLoRA Fine-Tuning](../08-fine-tuning/)
