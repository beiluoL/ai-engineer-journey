# Project 07 — Open Source LLM

## 项目目标

接触真实开源模型生态，在云端（Colab GPU）亲手跑通 Hugging Face 开源模型，理解加载 / 推理 / 量化 / 服务。

## 为什么做这个项目

生产环境不可能每次都调商业 API。需要掌握如何加载、运行、对比开源模型，理解它们的限制和优势。

## 解决什么问题

- 生产环境不能全靠商业 API
- 不知道怎么加载开源模型
- 不理解模型内存占用和推理速度

## 最终能力

```text
Model
    ↓
Tokenizer
    ↓
Weights
    ↓
Memory
    ↓
Inference
    ↓
Application
```

## 技术栈

- Hugging Face Transformers
- Tokenizer 深入理解
- Model Loading（device / dtype）
- Model Inference（生成参数 / 采样）
- 本地模型 Serving
- 量化基础

## 项目演进

```
Mini Transformer
    ↓ 接入开源生态
Open Source LLM v0.1（加载 + 推理）
    ↓ Generation + 本地 Serving
Open Source LLM v0.2
    ↓ 量化 + 应用
Open Source LLM v1.0
```

## 运行方式（Colab 云端，零本地资源）

> 路线决策（2026-09-29）：原计划在本机 M1 装 torch + 下模型，但本机磁盘仅剩 ~15GB 且用户要求「不要使用本地」。
> 改为 **Colab 云端真跑**：模型与算力都在 Colab 免费 T4 GPU 上，本机零磁盘/内存占用。
> 详见 [`notebooks/README.md`](notebooks/README.md) 与 [`notebooks/p07_colab.ipynb`](notebooks/p07_colab.ipynb)。
>
> **微调路线（Java 面试专家）**：在 Colab 免费 GPU 上用 LLaMA-Factory 对 Qwen2.5-1.5B 做 QLoRA SFT，产出 LoRA Adapter 并合并成完整模型。详见 [`notebooks/p07_finetune_java_interview.ipynb`](notebooks/p07_finetune_java_interview.ipynb) 与 [`scripts/`](scripts/)。
>
> **调用管线 `pipelines/`（当前主线，已真实跑通）**：本机跑不动 7B 权重（bf16 需 14.18 GiB），
> 但「调用」不需要本地有卡。`pipelines/` 走 DeepSeek OpenAI 兼容接口、由本机直接驱动，
> 6 个模块全部真实运行完毕，产出 6 张真实终端截图。详见 [`pipelines/README.md`](pipelines/README.md)。

```text
本机（只写代码）          Colab（跑模型）
   notebooks/        →   打开 p07_colab.ipynb
   p07_colab.ipynb        Runtime=GPU, Run All
         ↓                      ↓
   回收真实输出       →    demos/out/colab_Mxx.txt
         ↓
   渲染截图 + 写 milestones/
```

```text
本机（自己就是执行者）  ←── pipelines/ 路线
   demos/demo_0X.py  →   真实调 DeepSeek API
         ↓
   demos/out/*_terminal.txt（真实输出）
         ↓
   assets/term-*.png（真实截图）→ pipelines/README.md
```

## Milestones

| # | Milestone | 核心能力 | 状态 |
|---|-----------|----------|------|
| 01 | Hugging Face | HF Ecosystem / Hub / Pipeline | ⬜ Colab 待跑 |
| 02 | Tokenizer | BPE / Token 编码 / decode / chat template | ⬜ Colab 待跑 |
| 03 | Model Loading | device / dtype / from_pretrained / 参数量 | ⬜ Colab 待跑 |
| 04 | Model Inference | generate / KV cache / 贪心 | ⬜ Colab 待跑 |
| 05 | Generation Parameters | temperature / top_p / top_k | ⬜ Colab 待跑 |
| 06 | Local Model Serving | pipeline / 延迟 / 吞吐 | ⬜ Colab 待跑 |
| 07 | Model Memory / VRAM | 权重 / KV cache / 实测显存 | ⬜ Colab 待跑 |
| 08 | Quantization | 4-bit（Colab=bitsandbytes；Mac 本地=GGUF+llama.cpp） | ⬜ Colab 待跑 |
| 09 | Open Source LLM Application | 迷你聊天应用 / 历史记忆 | ⬜ Colab 待跑 |

> M08 量化路线：云端 CUDA 用 `load_in_4bit`（bitsandbytes）真跑；Mac 本地无 CUDA，对应走 GGUF + llama.cpp。
>
> **微调 Track（独立分支，当前主线）**：`notebooks/p07_finetune_java_interview.ipynb` 覆盖「数据集 → SFT → LoRA → QLoRA → GPU 训练 → 评估 → 合并」全流程，目标产出 Java 面试专家模型。Colab 侧脚本见 `scripts/`，训练数据见 `data/java_interview.json`（**59 条**真实 Java 面试问答）。

> **已真实跑通的部分见 `pipelines/`**（可与上表对照）：M05 生成参数、M07 显存/参数量、M09 应用
> 已有本地真实证据；M03 模型加载、M08 量化因需要 GPU/本地权重，仍依赖 `notebooks/` 那条线。

## 当前状态

🔄 进行中。三条线的落地情况：

| 线 | 状态 | 说明 |
|---|---|---|
| `pipelines/` 调用管线 | ✅ **已真实跑通** | 6 个模块真实运行，6 张终端截图 + 12 份产物 |
| `notebooks/p07_colab.ipynb` 推理 | ⬜ 待跑 | 需用户在 Colab 分配 GPU 并回收输出 |
| `p07_finetune_java_interview.ipynb` 微调 | ⬜ 待跑 | 需用户在 Colab 跑 QLoRA SFT |

## 当前版本

v0.1 —— `pipelines/` 调用管线 6 个模块全部真实跑通（含手算参数量对账、显存账本、RAG-lite 检索评测），
产出 6 张真实终端截图。

## 项目结构

```
projects/07-open-source-llm/
├── README.md                     # 本文件
├── data/
│   └── java_interview.json       # 59 条真实 Java 面试问答（SFT 训练集）
├── scripts/                      # Colab 侧脚本（由 notebook wget 后调用）
│   ├── colab_download_model.py   # 下载基座模型 Qwen2.5-1.5B
│   ├── colab_prepare.py          # 数据集下载 + 注册 + 训练/合并 YAML
│   └── colab_eval.py             # 微调前后对比评测
├── notebooks/
│   ├── p07_colab.ipynb                   # 推理路线：M01-M09 全覆盖（待用户 Colab 跑）
│   ├── p07_finetune_java_interview.ipynb # 微调路线：QLoRA SFT 全流程（待用户 Colab 跑）
│   ├── build_p07_notebook.py             # 推理 notebook 生成脚本
│   └── README.md                         # Colab 使用 + 输出回收说明
├── pipelines/                   # 【主线】本地驱动的调用管线，已真实跑通
│   ├── README.md                # 路线说明 + 数据可信度分级 + 6 张真实截图
│   ├── data/open_models_weights.json  # 真实抓取的 HF config.json（fetch_status: all_ok）
│   ├── llm_client/              # 零依赖客户端（client.py）+ 资源算术（baselines.py）
│   ├── demos/ + demos/out/      # 6 个 demo + 12 份真实运行产物
│   └── assets/term-0X-*.png     # 6 张真实终端截图
├── src/                         # （后续可放可复用封装）
├── demos/out/                   # 回收的 Colab 真实输出（colab_Mxx.txt / 微调前后对比）
├── assets/                      # Colab 路线截图
└── milestones/                  # 01-09 文档（待 Colab 跑通后撰写）
```

## 已掌握能力

- Project 01-06 的所有能力

## 下一步

完成 Project 06，然后进入开源模型生态。

**前置项目**：[Project 06 — Mini Transformer / LLM](../06-mini-transformer-llm/)
