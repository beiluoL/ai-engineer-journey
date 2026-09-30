# AI Engineer Journey — Roadmap

> 10 个连续项目，逐步构建 AI Engineer 完整能力体系。

## 能力递进关系

```text
Python              ← Project 01-02（脚本 → 服务）
  ↓
LLM Application     ← Project 03（Prompt / Streaming / Tool Calling）
  ↓
RAG                 ← Project 04（Embedding / Vector DB / Retrieval）
  ↓
Agent / MCP          ← Project 05（Tool / Agent Loop / MCP Protocol）
  ↓
模型原理            ← Project 06（PyTorch / Attention / Transformer）
  ↓
开源生态            ← Project 07（Hugging Face / 本地推理）
  ↓
微调                ← Project 08（SFT / LoRA / QLoRA）
  ↓
评估 + 服务化       ← Project 09（Benchmark / Quantization / vLLM）
  ↓
综合实现            ← Project 10（从零实现 Tiny LLM）
```

联系描述：

前面的项目提供后续项目所需基础能力。Project 01 学会 Python、HTTP 和真实 LLM API；Project 02 将其工程化；Project 03 在此之上构建 AI Application；Project 04 为应用增加外部知识；Project 05 让模型拥有工具和执行能力；Project 06 开始进入模型内部；Project 07 使用真实开源模型；Project 08 修改模型能力；Project 09 解决生产级评估与推理；Project 10 将这些能力重新组合。

---

## Project 01 — Python AI CLI Assistant

**目标**：通过持续升级一个 AI CLI Assistant，学习 Python 基础，并最终接入真实 LLM API。

**核心技术**：Variables / List Dict JSON / Condition Loop / Function / Module Package / Exception / File JSON / venv pip / HTTP API / Real LLM

**最终交付**：v1.0 的 CLI AI Assistant（能真实调用 LLM）

**状态**：🔄 进行中

**10 个 Milestone**：
```
01 — Variables
02 — List / Dict / JSON
03 — Condition / Loop
04 — Function
05 — Module / Package
06 — Exception
07 — File / JSON Persistence
08 — venv / pip / Environment
09 — HTTP / API
10 — Real LLM API
```

---

## Project 02 — Engineering AI Assistant

**目标**：在 Project 01 基础上，把 CLI Assistant 从 Python Script 工程化为 Python Application。

**核心技术**：Async / Type Hints / Dataclass / Config / Logging / Testing / FastAPI

**最终交付**：HTTP 服务化的 AI Assistant Service

**状态**：⬜ 未开始

**10 个 Milestone**：
```
00 — Classes and OOP
01 — Async / Await
02 — Async HTTP Client
03 — Type Hints
04 — Dataclass
05 — Config / Environment
06 — Logging
07 — Testing / Debugging
08 — Packaging
09 — FastAPI
```

---

## Project 03 — AI Application

**目标**：进入真正的 LLM Application【大模型应用】开发。

**核心技术**：Prompt / Structured Output / Streaming / Function Calling / Conversation Memory

**最终交付**：Web 端 AI Chat 应用

**状态**：✅ 9/9 Milestone 成文 + `src/` 代码落地 + 61 项离线测试全绿

**9 个 Milestone**：
```
01 — Prompt
02 — System / User / Assistant Messages
03 — Structured Output
04 — Streaming
05 — Conversation Memory
06 — Model Parameters
07 — Token / Context Window
08 — Function Calling
09 — AI Application Architecture
```

---

## Project 04 — AI Knowledge Base / RAG Assistant

**目标**：构建真正的 AI Knowledge Base【AI 知识库】与 RAG【检索增强生成】系统。

**核心技术**：Document Ingestion / Chunking / Embedding / Vector Database / Retrieval / Rerank

**最终交付**：接入个人知识库的 RAG Assistant

**状态**：✅ 17/17 Milestone 成文 · ✅ src/rag/ + `web/` 落地（19 模块 + 零构建前端） · ✅ 197 项 pytest 离线全绿 · ✅ 44 张真实运行截图

**17 个 Milestone**：
```
01 — Document Ingestion
02 — Chunking
03 — Embedding
04 — Vector Database
05 — Retrieval
06 — Similarity Search
07 — Rerank
08 — Context Assembly
09 — RAG Pipeline
10 — RAG Evaluation
11 — Real Service Integration
12 — Real LLM Integration
13 — FastAPI Web API
14 — Real RAG Evaluation
15 — Observability
16 — Real Reranker & Calibration
17 — Chat UI & Session History
```

---

## Project 05 — Research Agent / MCP Assistant

**目标**：让 AI 从"回答问题"变成能调用外部工具、执行多步骤任务的 Agent【智能体】。

**核心技术**：Tool / Tool Schema / Function Calling / Agent Loop / MCP Protocol

**最终交付**：能自主规划和调用工具的 Agent System

**状态**：✅ 已完成（10/10 Milestone，v1.0 收官）

**10 个 Milestone**：
```
01 — Tool                  ✅ 工具三件套 / ToolResult / 检索即工具 / ast 沙箱
02 — Tool Schema          ✅ JSON Schema / 签名推导 / 参数纠偏
03 — Function Calling     ✅ tool 消息三字段 / 协议顺序 / 真实链路三坑
04 — Agent                ✅ ReAct 循环 / 三道闸门 / 轨迹落盘 / CLI 入口
05 — Agent Loop           ✅ 工作记忆裁剪 / 草稿纸 / 第三道闸门 / 多步骤任务
06 — Multi-Step Task      ✅ 显式 Plan / 依赖拓扑 / 失败传播 / 计划工具
07 — MCP                  ✅ JSON-RPC 2.0 / 四种消息 / stdio 帧格式
08 — MCP Server           ✅ 工具跨进程暴露 / 两类错误 / 错误码选择
09 — MCP Client           ✅ 握手 / Schema 转换 / 桥接进 ToolRegistry
10 — Agent Workflow       ✅ 多 Worker 编排 / 上下文隔离 / 规模扫描
```

---

## Project 06 — Mini Transformer / LLM

**目标**：从 AI 应用层进入模型内部，从零构建 Mini Transformer Decoder。

**核心技术**：纯 numpy（刻意不引入 torch）/ 从零 Autograd / Self-Attention / Multi-Head Attention / Transformer Decoder

**最终交付**：从零构建的 Mini Transformer Decoder

**状态**：✅ 已完成（10/10 Milestone，v1.0 收官）

> 备注：本项目刻意**不引入 PyTorch**（README 有说明），核心实现用纯 numpy 手写，包括从零的自动微分（autograd）。Milestone 实际执行顺序为「架构优先」：M01 架构 → M02 Tokenizer → M03-M10 模型全链路（Embedding / Attention / Multi-Head / Block / Decoder / DataLoader / Training / Inference）。

**10 个 Milestone（实际落地）**：
```
01 — Project Architecture  ✅ 五层契约 / 目录约定 / 手写架构图
02 — Tokenizer            ✅ 字符级 + BPE 双实现 / 往返一致性 / 词表增长曲线
03 — Embedding            ✅ 查表 Embedding + 正弦位置编码 + combine
04 — Attention            ✅ softmax(QKᵀ/√d)V 手写 + 因果掩码
05 — Multi-Head Attention ✅ 分头 / 拼接 / 输出线性映射
06 — Transformer Block    ✅ Pre-LN + 残差 + FFN
07 — Decoder Stacking     ✅ 因果掩码 + N 层堆叠 + 输出投影
08 — Dataset / DataLoader ✅ 滑窗采样 / batch / pad / mask
09 — Training Loop        ✅ 从零 autograd 反传 + 交叉熵 + 优化器（loss 6.21→4.75）
10 — Inference / Sampling ✅ greedy / temperature / top-k 生成
```

---

## Project 07 — Open Source LLM

**目标**：接触真实开源模型生态，在本地跑通 Hugging Face 模型。

**核心技术**：Hugging Face / Tokenizer / Model Loading / Inference / Quantization

**最终交付**：本地跑通的开源 LLM 应用

**状态**：🔄 进行中（v0.1）

> 本机 M1 磁盘仅剩 ~15GB，而 Qwen2.5-7B 的 bf16 权重就要 **14.18 GiB**，
> 所以本项目拆成两条互不干扰的线：
> - **`pipelines/`（已真实跑通）** —— 调用、生成参数、资源测算。
>   不需要本地有卡，走 DeepSeek OpenAI 兼容接口由本机直连驱动，已产出 6 张真实终端截图。
> - **`notebooks/`（待 Colab GPU）** —— 模型加载、量化这类必须摸到真实权重 / 需要 GPU 的部分。

**9 个 Milestone**：
```
01 — Hugging Face              🔶 已用真实抓取的 HF config.json 做参数账本；Hub 生态部分待 Colab
02 — Tokenizer                 🔶 已对照「本地估算 vs 服务端 usage」（40 vs 34）；BPE 细节待跑
03 — Model Loading             ⬜ 需要 GPU/权重（Colab 路线）
04 — Model Inference           ✅ 真实调用 + usage 守恒校验（pipelines M01）
05 — Generation Parameters     ✅ temperature 0/0.7/1.5 四组对照实测（pipelines M03）
06 — Local Model Serving       🔶 已实测 SSE 流式 / TTFT / 吞吐；真正起服务待 Colab
07 — Model Memory / VRAM       ✅ 手算参数量对账 + 权重 & KV Cache 显存账本（pipelines M04、M05）
08 — Quantization              ⬜ 需要权重（Colab=bitsandbytes 4bit / Mac=GGUF+llama.cpp）
09 — Open Source LLM Application  ✅ Java 面试助手（检索 + 生成）端到端跑通（pipelines M06）
```

> ⚠️ 一个实测反例已记入 `pipelines/README.md`：temperature=0 连续两次调用**结果不一致**
> （68 vs 72 tokens）——「贪婪解码 ⇒ 严格确定性」是近似成立而非保证。

---

## Project 08 — LoRA / QLoRA Fine-Tuning

**目标**：进入模型微调，让通用模型变成领域模型。

**核心技术**：SFT / PEFT / LoRA / QLoRA / Dataset Preparation / Training

**最终交付**：自己微调的领域模型

**状态**：✅ 已完成（v1.0，9/9 Milestone，189 项 pytest 全绿）

**9 个 Milestone**：
```
01 — Fine-Tuning                  ✅ 全量 vs LoRA 开销对比（可训练 10.53% / 显存 36.76%）
02 — Dataset Preparation          ✅ Alpaca 59 条 / 答案区占比 81.41% / 词表 1024
03 — Instruction Tuning           ✅ 只在答案区算 loss，困惑度再降 6.64%
04 — LoRA                         ✅ 手写 W+(α/r)·B·A；B=0 等价性误差 0.000e+00；grad_check 6.585e-05
05 — QLoRA                        ✅ NF4 分位量化 + 双量化；压缩 7.75×，相对误差 0.0914
06 — Training Configuration       ✅ rank / lr / alpha 真实扫描，最优 r=8 alpha=16 lr=0.01
07 — Checkpoint                   ✅ adapter 115.76 KB vs 基座 901 KB（7.8×）；续训逐点差 1.290e-04
08 — Merge / Load Adapter         ✅ 合并前后最大绝对误差 0.000e+00
09 — Fine-Tuned Model Evaluation  ✅ 域内困惑度 3649.9 → 421.1（↓88.46%）+ 遗忘检查
```

> 实现说明：本机 M1 无 CUDA、磁盘余量紧张，故本项目走**纯 numpy 手写**路线——
> 复用 Project 06 手写的 Transformer 与自动微分作为基座，在其上从零实现 LoRA / NF4 / QLoRA。
> 好处是每一步都能用有限差分对拍验证、每个数字都是实测；代价是不接触 GPU 上的真实 7B 模型，
> 涉及大规模的部分（如 7B 显存）在文档中明确标注为「按同一公式外推」，不伪装成实测。

---

## Project 09 — LLM Evaluation / Inference Platform

**目标**：掌握模型评估、量化和高性能推理服务化。

**核心技术**：Benchmark / 自动评估 / INT8 INT4 量化 / vLLM / Batching / PagedAttention

**最终交付**：高性能推理服务平台

**状态**：✅ 已完成（v1.0，11/11 Milestone，229 项 pytest 全绿）

**11 个 Milestone**：
```
01 — Evaluation             ✅ 困惑度之外：Token Acc 6.05% / ECE 0.0927 / 覆盖率 99.31%
02 — Benchmark              ✅ 任务集 + 排行（94.38 > 75.56 > 21.87）
03 — Evaluation Dataset     ✅ held-out 12 条、与训练集 instruction 交集 0（防泄漏）
04 — Automatic Evaluation   ✅ 零 LLM 规则评分（94.09 > 86.03 > 55.02 > 0.00）
05 — Model Comparison       ✅ 多种子配对 bootstrap，相对基座 10/0/0 稳定
06 — Quantization           ✅ INT8/INT4/NF4 三方；端到端 NF4 反而最优（−4.088%）
07 — Inference Engine       ✅ 手写自回归引擎，KV Cache 6.155→2.794 ms（2.20×）
08 — vLLM / PagedAttention  ✅ 分块 KV：浪费率 76.4%→16.0%，省 71.9%
09 — Batching               ✅ Continuous vs Static：吞吐 1.52×、p95 −43.5%
10 — KV Cache               ✅ 显存账本 57,344 B/token；batch16@32K 达权重 197.46%
11 — Model Serving          ✅ 标准库 HTTP 服务 + SSE 流式 + 并发 4/4 + metrics
```

> 实现说明：与 Project 08 同源——本机 M1 无 CUDA、磁盘余量紧张，故走**纯 numpy + Python 标准库手写**
> （HTTP 服务直接用 `http.server` + `urllib`，不引 fastapi/vllm 等第三方包）。
> 基座与微调产物复用 P06（手写 Transformer + autograd）与 P08（LoRA / NF4 / 冻结基座），
> 保证评估对象与 P08 微调出的模型是同一个，比较才有意义。
> 边界已在文档中诚实标注：PagedAttention / Batching 为块级账本与离散事件仿真（非真实 GPU 分配）；
> 7B 显存数字为按架构公式计算（与 P07 独立计算交叉验证），非本机实测。

---

## Project 10 — Tiny LLM / AI Engineer Capstone

**目标**：把前面所有能力重新串起来，完成最终 AI Engineer Capstone【综合项目】。

**核心技术**：Tokenizer → Embedding → Transformer → Training → Evaluation → Inference → Serving

**最终交付**：从零实现的小型 LLM 完整工程

**状态**：✅ 已完成（v1.0，11/11 Milestone，71 项 pytest 全绿）

**11 个 Milestone**：
```
01 — Project Architecture  ✅ 唯一配置入口 TinyConfig + validate() / 八段流水线
02 — Tokenizer            ✅ 手写 BPE vocab=1280；压缩 1.445 字/token；roundtrip 失败全归因 OOV
03 — Dataset              ✅ 泄漏检查 overlap=0；滑动窗口打包 206 train / 37 val
04 — Embedding            ✅ 查表=one-hot@W 误差 0.000e+00；正弦 PE 0 参数；词表占 35.6%
05 — Transformer Block    ✅ 因果自检过去 0.000e+00 / 未来 1.191e+01；掩码反例 argmax 同为 676
06 — Training             ✅ train 7.1547→3.6882 / val 5.7551（第 800 步）→5.8234；早停回滚
07 — Evaluation           ✅ 三层评估；PPL 315.79 / ECE 0.0662 / 关键词覆盖 0.000；配对 37/0/0、24/13/0
08 — Inference            ✅ 采样四旋钮；KV Cache 等价 3.442e-15；真流式 TTFT 0.20 ms / 总 4.73 ms
09 — Optimization         ✅ INT8 3.85×/ΔPPL +0.08%、INT4 7.42×/+2.66%、NF4 7.75×/+4.01%；KV 512 B/token
10 — Serving              ✅ OpenAI 兼容 + SSE；冒烟四项全过；并发 4 吞吐 130.60 req/s
11 — Complete System      ✅ 八段一条命令跑完；可缓存 0.928 s / 可分段 / report.json 可机读
```

> 实现说明：与 P06/P08/P09 同源——**纯 numpy + Python 标准库手写**，不引入 torch / transformers / fastapi / vllm，
> 通过 `src/tiny/paths.py` **三层复用**前面项目的已验真能力：P06（手写 Tensor/autograd + `TransformerLM` + BPE）
> + P08（`enable_deterministic_autograd()` 确定性补丁）+ P09（评估指标 / 量化 / KV 账本 / HTTP 服务）。
>
> Capstone 的交付物不是模型，而是一条**可缓存、可分段重跑、报告可机读**的流水线。
> 边界已诚实标注：这个 230K 参数 + 6,384 训练 token 的模型**会拼词、不会答题**（生成层关键词覆盖 0.000），
> 这正是「三层评估」存在的理由——把真相量化出来，而不是让 loss 曲线替它遮羞。

---

## 附 — 基础知识层：llm-fundamentals

**目标**：把大模型基础理论系统整理成一份由浅入深的学习笔记，讲清「**为什么这么设计**」。

**与 10 个项目的关系**：不属于 Project 序号体系，是与之平行的**理论层**。
`projects/*/milestones/` 回答「怎么跑起来」，`llm-fundamentals/` 回答「原理是什么、为什么」。两者互相引用，不重复正文。

**状态**：✅ 已完成（11 章 + 8 个可运行 demo + 13 张可复现配图）

**11 章**：
```text
01 — 语言模型基础      ✅ token → embedding → logits → 概率 → 交叉熵 / PPL 全链路
02 — 注意力机制        ✅ QKV / √d_k 缩放推导 / 两类掩码 / 多头 / MHA-GQA-MQA
03 — Transformer 架构  ✅ Pre-LN / RMSNorm / SwiGLU FFN / 位置编码 / 张量形状表
04 — 预训练            ✅ 数据流水线 / CLM-MLM-FIM / 并行策略 / BF16 / 算力与成本账
05 — 微调              ✅ SFT（loss mask / chat template 坑）/ LoRA / QLoRA / 灾难性遗忘
06 — 涌现与缩放定律    ✅ Kaplan / Chinchilla / 涌现是否伪影 / 过度训练的经济学
07 — 解码与推理        ✅ Prefill-Decode / 采样策略 / KV Cache / 量化 / 引擎选型
08 — 对齐              ✅ RLHF 三阶段 / Bradley-Terry / PPO 目标 / DPO 推导 / reward hacking
09 — 数学基础          ✅ 符号表 + 10 个关键推导（√d_k 方差、p−y 梯度、RoPE 正交性）
10 — 术语表            ✅ 8 组 150+ 条中英对照，含「最容易混的六组」
11 — 开源项目          ✅ 10 个项目对应到具体章节 + 跑通标志
```

**入口**：[`llm-fundamentals/README.md`](llm-fundamentals/README.md)
