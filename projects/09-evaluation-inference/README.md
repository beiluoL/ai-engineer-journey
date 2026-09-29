# Project 09 — LLM Evaluation / Inference Platform

## 项目目标

掌握模型评估、量化和高性能推理服务化。

## 为什么做这个项目

训练完模型只是第一步。上线前必须评估效果、量化压缩、做高性能推理服务——这些是 AI 工程师区别于调参侠的关键能力。

## 解决什么问题

- 不知道模型效果好不好（评估）
- 模型太大跑不动（量化）
- 推理太慢无法并发（高性能 Serving）

## 最终能力

```text
Model
    ↓
Evaluation
    ↓
Optimization
    ↓
Inference
    ↓
Serving
```

## 技术栈

- **纯 numpy + Python 标准库手写**：评估指标、Benchmark、量化、推理引擎、PagedAttention、Batching、HTTP 服务
- 不引入 torch / transformers / fastapi / vllm —— HTTP 服务直接用标准库 `http.server` + `urllib`
- 基座与微调产物复用 Project 06（手写 Transformer + autograd）与 Project 08（LoRA / NF4 / 冻结基座）

## 项目演进

```
Fine-tuned Model
    ↓ 评估
Evaluation Platform v0.1
    ↓ 量化
Evaluation Platform v0.2
    ↓ vLLM Serving
Evaluation & Inference Platform v1.0   ✅
```

## Milestones

| # | Milestone | 核心能力 | 状态 |
|---|-----------|----------|------|
| 01 | Evaluation | 困惑度之外：Token Acc / ECE 校准 / 覆盖率 | ✅ 已落地 |
| 02 | Benchmark | 任务集 + 打分 + 汇总排行 | ✅ 已落地 |
| 03 | Evaluation Dataset | held-out 切分 + **泄漏检查** | ✅ 已落地 |
| 04 | Automatic Evaluation | 零 LLM 参与的规则化自动评分 | ✅ 已落地 |
| 05 | Model Comparison | 多种子配对 bootstrap 比较 | ✅ 已落地 |
| 06 | Quantization | INT8 / INT4 / NF4 三方对比 + 端到端代价 | ✅ 已落地 |
| 07 | Inference Engine | 手写自回归引擎 + KV Cache 开关 | ✅ 已落地 |
| 08 | vLLM / PagedAttention | 分块 KV 管理 / block table / 浪费率 | ✅ 已落地 |
| 09 | Batching | Static vs Continuous Batching 仿真 | ✅ 已落地 |
| 10 | KV Cache | 显存账本 + 何时反超权重 | ✅ 已落地 |
| 11 | Model Serving | 标准库 HTTP 服务 + SSE 流式 + metrics | ✅ 已落地 |

## 当前状态

**v1.0 —— 11/11 Milestone 全部落地，229 项 pytest 全绿，11 个真实 demo，11 张真实终端截图 + 11 张手写架构图。**

主线叙事：**训出来的模型好不好？怎么让它跑得快、跑得起、服务得出去？**
评估体系 → 压模型（量化）→ 压延迟（引擎 / KV Cache / PagedAttention / Continuous Batching）→ 服务化。

### 关键实测数字

| 维度 | 实测结果 |
|---|---|
| 困惑度 vs 准确率 | 答案区 PPL **5496.76**，但 Token Acc 仅 **6.05%** —— 困惑度好看不等于能用 |
| 校准 | **ECE 0.0927**（全序列 PPL 5500.51，覆盖率 99.31%） |
| 防泄漏 | 训练 47 / held-out **12**，instruction 交集 **0** |
| 自动评分排行 | 参考答案 94.09 > 首句摘要 86.03 > 重复回答 55.02 > 空回答 0.00 |
| 配对比较 | adapter/merge **6.5349±0.0469**、INT8 6.5351±0.0468、基座 **8.6637±0.2460**；相对基座 **10/0/0 稳定** |
| 量化三方 | INT8 MSE 7.67e-08(3.76×) / INT4 2.52e-05(7.11×) / NF4 5.25e-05(7.75×) |
| KV Cache 加速 | 无 KV **6.155 ms** → 有 KV **2.794 ms**，**2.20×**；输出 id 全等，logits 误差 4.441e-15 |
| PagedAttention | 预分配 **1024.0 KiB** → 分页 **288.0 KiB**；浪费率 **76.4% → 16.0%**（省 71.9%） |
| Continuous Batching | 1788.27 → **2709.50 req/s**（**1.52×**），延迟 −51.8%，p95 −43.5%，空闲率 45.0%→16.7% |
| KV 显存账本 | 7B：57,344 B/token、权重 14.18 GiB；batch16@seq32768 时 KV 达权重 **197.46%** |
| 服务化 | 4 并发 **4/4**；metrics 请求 6 / 错误 0 / p95 **3.311 ms** / **2046.08 token/s** |

### 最值得记住的一条：**权重误差最小 ≠ 端到端最优**

量化方案不能只看重建误差来选。本项目实测：

- **NF4** 权重 MSE 最差（5.246e-05，是 INT8 的 **684 倍**），但端到端 PPL 反而**最好**（**−4.088%**，降 224.71）
- **INT8** 权重 MSE 最小（7.67e-08），端到端却只有 **−0.028%**

→ 结论：量化一定要在**真实任务集上复测**，MSE 只是参考。

### 其他反直觉发现

- **小模型上 KV Cache 只有 2.20×**：d_model=64、2 层，Python 对象开销吃掉大半。**别拿这个数去推大模型**。
- **adapter vs merge 的 0/0/10 全平**不是数据缺失，而是「合并等价性」的正面证据。
- **macOS 的 HTTP_PROXY 会拦 localhost**：必须用 `ProxyHandler({})` 显式禁用代理才连得上自己的服务。

### 诚实标注的口径边界

- PagedAttention / Batching 是**块级账本与离散事件仿真**，不是真实 GPU 分配；1.52× 是乐观上界。
- M10 的 7B 数字是**按架构公式计算**（与 P07 独立计算交叉验证），非本机实测。
- 服务后端挂的是玩具模型（d_model=64），不是 7B。
- adapter 只训 24 步（图快速可复现），绝对指标难看，但**比较结论有效**。

## 当前版本

v1.0

## 项目结构

```text
projects/09-evaluation-inference/
├── README.md                  # 本文件
├── src/ie/                    # 13 个手写模块
│   ├── paths.py               # 跨项目导入 P06/P08 + 确定性开关
│   ├── metrics.py             # 困惑度 / Token Acc / ECE 校准 / 覆盖率
│   ├── benchmark.py           # 任务集 + 打分 + 汇总排行
│   ├── evalset.py             # held-out 切分 + 去重 + 泄漏检查
│   ├── autoeval.py            # 零 LLM 的规则化自动评分
│   ├── compare.py             # 多种子配对 bootstrap 比较
│   ├── quantize.py            # INT8 / INT4（per-tensor + per-channel）+ 与 NF4 对比
│   ├── engine.py              # 手写自回归推理引擎（KV Cache 可开关）
│   ├── paged.py               # PagedAttention 分块 KV 管理 + block table
│   ├── batching.py            # Static vs Continuous Batching 仿真
│   ├── kvbook.py              # KV Cache 显存账本
│   └── serve.py               # 标准库 HTTP 服务（OpenAI 兼容 + SSE + metrics）
├── tests/                     # 229 项 pytest 全绿
├── demos/                     # 11 个真实可跑 demo（01-11 对应 11 个 Milestone）
│   └── out/*_terminal.txt     # 真实输出（文档里所有数字都来自这里）
├── assets/                    # 11 张真实终端截图 + 11 张手写架构图 SVG
├── milestones/                # 01-11 文档
└── models/                    # P09 自有产物（adapter / 量化权重），不碰 P08 缓存
```

## 运行方式

```bash
# 跑测试（229 passed）
/Users/beiluo/.workbuddy/binaries/python/envs/default/bin/python -m pytest -q

# 跑任意一个 demo（输出同时打到终端和 demos/out/*.txt）
/Users/beiluo/.workbuddy/binaries/python/envs/default/bin/python demos/demo_08_paged_attention.py
```

> 本项目刻意**不建 venv**：统一复用带 numpy 的托管解释器，省磁盘空间。

## 已掌握能力

- Project 01-08 的所有能力
- 从零搭建评估体系（困惑度之外还要看准确率与校准）、构建防泄漏评估集、多种子配对比较
- 手写 INT8/INT4 量化并用端到端任务复测其代价
- 手写推理引擎、KV Cache、PagedAttention 分块管理、Continuous Batching 仿真
- 用标准库起 OpenAI 兼容的推理服务（SSE 流式 + 并发 + metrics）

## 下一步

Project 10 —— Tiny LLM / AI Engineer Capstone（把 P06→P09 全部能力重新串成完整工程）。

**前置项目**：[Project 08 — LoRA / QLoRA Fine-Tuning](../08-fine-tuning/)
**底座来源**：[Project 06 — Mini Transformer / LLM](../06-mini-transformer-llm/)
