# -*- coding: utf-8 -*-
"""生成 P07 的 Colab notebook：M01-M09 全覆盖，真实可跑。"""
import json, os

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

cells = []

def md(src):
    cells.append({"cell_type": "markdown",
                  "metadata": {},
                  "source": src.splitlines(keepends=True)})

def code(src):
    cells.append({"cell_type": "code",
                  "metadata": {},
                  "execution_count": None,
                  "outputs": [],
                  "source": src.splitlines(keepends=True)})

# ---------------- 标题 ----------------
md("""# Project 07 — Open Source LLM（Colab 云端真跑版）

> 本 notebook 在 **Google Colab（GPU runtime）** 一键 `Run All` 即可跑通 P07 全部 9 个 Milestone。
> 目标：接触真实开源模型生态、在云端 GPU 上亲手加载 / 推理 / 量化 / 服务一个开源 LLM（Qwen2.5-0.5B-Instruct）。

## 使用步骤（重要）
1. 顶部菜单 `Runtime → Change runtime type → Hardware accelerator = GPU`（T4 免费）。
2. `Runtime → Run all`。
3. 每节代码 cell 会打印**真实数字**（参数量、显存、延迟、生成文本）。请把这些输出贴回仓库的 `demos/out/colab_*.txt`，用于生成文档截图。
4. 全程不占用你本机磁盘与内存——模型与算力都在 Colab。

> 模型：`Qwen/Qwen2.5-0.5B-Instruct`（0.49B 参数，Apache-2.0 开源，支持 chat template）。
""")

# ---------------- 环境 / 设备 ----------------
md("""## 0. 环境准备与设备检测
Colab 已预装 torch / transformers；这里只确保版本够新，并检测 GPU。
""")
code("""# Colab 预装 torch/transformers；仅在有需要时升级（注释掉可跳过）
# !pip install -q -U transformers bitsandbytes

import torch, transformers, time, os
print("torch       :", torch.__version__)
print("transformers:", transformers.__version__)

device = "cuda" if torch.cuda.is_available() else "cpu"
print("device      :", device, "(Colab GPU runtime 下应为 cuda)")
if device == "cuda":
    print("GPU         :", torch.cuda.get_device_name(0))

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
""")

# ---------------- M01 ----------------
md("""## M01 · Hugging Face 生态
Hugging Face Hub 是开源模型的「GitHub」：`from_pretrained` 负责从 Hub 拉取权重与配置文件，
`pipeline` 是高层封装，`~/.cache/huggingface` 是本地缓存（同一模型只下一份）。
""")
code("""from huggingface_hub import list_models, model_info

# 1) 在 Hub 上检索开源模型（真实请求）
print("=== Hub 检索 'Qwen' 前 5 个 ===")
for m in list_models(search="Qwen", limit=5):
    print(f"  {m.id:38s} downloads={m.downloads:>9,}  likes={m.likes}")

# 2) 读取模型卡元信息（不下载权重）
info = model_info(MODEL_ID)
print("\\n=== model_info:", MODEL_ID, "===")
print("  pipeline_tag:", info.pipeline_tag)
print("  downloads   :", info.downloads)
print("  likes       :", info.likes)
print("  tags        :", info.tags[:6])

# 3) 缓存根目录
print("\\nHF 缓存根目录:", os.path.expanduser("~/.cache/huggingface"))
""")

# ---------------- M02 ----------------
md("""## M02 · Tokenizer 深入理解
用 `AutoTokenizer` 真实分词，观察 id / token 文本 / 特殊 token，并用 chat template 把对话拼成模型输入。
（对照 P06：我们那时是从零手写的 BPE；这里用工业级 BPE/Byte-level BPE。）
""")
code("""from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained(MODEL_ID)

text = "Transformer 是一种神经网络架构，2017 年被提出。"
ids = tok.encode(text)
print("文本     :", text)
print("token 数 :", len(ids))
print("token ids:", ids[:24], "..." if len(ids) > 24 else "")
print("tokens   :", tok.convert_ids_to_tokens(ids))
print("decode 回:", tok.decode(ids))

print("\\n特殊 token:")
print("  bos:", tok.bos_token, "| eos:", tok.eos_token, "| pad:", tok.pad_token)

# chat template：把对话拼成训练时的格式
messages = [{"role": "user", "content": "用一句话解释什么是大语言模型。"}]
prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print("\\n=== chat template 后的 prompt ===\\n" + prompt)
""")

# ---------------- M03 ----------------
md("""## M03 · Model Loading 加载
`AutoModelForCausalLM.from_pretrained` 加载权重；`torch_dtype="auto"` 保留官方 dtype，
`device_map="auto"` 自动放到 GPU。打印参数量、每层形状、权重字节数。
""")
code("""from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype="auto", device_map="auto")

total     = sum(p.numel() for p in model.parameters())
trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
print("总参数量       :", f"{total:,}")
print("可训练参数量   :", f"{trainable:,}")
print("num_layers     :", model.config.num_hidden_layers)
print("hidden_size    :", model.config.hidden_size)
print("attn_heads     :", model.config.num_attention_heads)
print("kv_heads(GQA)  :", getattr(model.config, "num_key_value_heads", None))
print("vocab_size     :", model.config.vocab_size)
print("max_position   :", model.config.max_position_embeddings)

print("\\n=== 前 4 个参数张量形状 ===")
for name, p in list(model.named_parameters())[:4]:
    print(f"  {name:48s} {tuple(p.shape)} {p.dtype}")

dt = next(model.parameters()).dtype
bpp = torch.finfo(dt).bits // 8 if dt.is_floating_point else 1
print(f"\\n权重 dtype={dt}, 每参数 {bpp}B -> 权重约 {total*bpp/1e9:.2f} GB")
""")

# ---------------- M04 ----------------
md("""## M04 · Model Inference 推理
`model.generate()` 自回归生成。`do_sample=False` 即贪心。内部复用 **KV cache**（past_key_values），
避免每步重算历史 key/value。
""")
code("""input_text = "法国的首都是"
inputs = tok(input_text, return_tensors="pt").to(device)
print("input_ids shape:", tuple(inputs.input_ids.shape))

t0 = time.time()
out = model.generate(**inputs, max_new_tokens=40, do_sample=False)
dt_gen = time.time() - t0
print(f"贪心生成耗时: {dt_gen:.2f}s")
print("生成结果:", tok.decode(out[0], skip_special_tokens=True))

print("\\n说明: generate 内部复用 past_key_values(KV cache)，每步只算新 token 的注意力。")
""")

# ---------------- M05 ----------------
md("""## M05 · Generation Parameters 生成参数
`temperature` 控制随机度（0=贪心确定）、`top_p` 核采样、`top_k` 截断、`repetition_penalty` 抑制重复。
同一 prompt 不同参数生成不同结果。
""")
code("""prompt = "请写一句关于秋天的短诗："
inputs = tok(prompt, return_tensors="pt").to(device)
print("prompt:", prompt, "\\n")

for temp in [0.0, 0.7, 1.2]:
    for top_p in [1.0, 0.9]:
        out = model.generate(**inputs, max_new_tokens=30,
                             do_sample=temp > 0, temperature=temp, top_p=top_p)
        gen = tok.decode(out[0], skip_special_tokens=True).replace("\\n", " ")
        print(f"[temp={temp} top_p={top_p}] {gen}\\n")
""")

# ---------------- M06 ----------------
md("""## M06 · Local Model Serving 本地服务
把模型封装成 `pipeline`（等价于本地推理服务的核心），并发多请求测延迟与吞吐。
生产级可用 **HF TGI / vLLM** 做连续批处理（continuous batching）。
""")
code("""from transformers import pipeline

gen = pipeline("text-generation", model=model, tokenizer=tok,
               device=0 if device == "cuda" else -1)

reqs = ["你好，介绍一下你自己。", "1 + 1 等于几？", "用 Python 写一个快速排序。"]
latencies = []
for r in reqs:
    t0 = time.time()
    res = gen(r, max_new_tokens=40)
    latencies.append(time.time() - t0)
    print(f"[{latencies[-1]:.2f}s] {r} -> {res[0]['generated_text'][:50]}...")

print(f"\\n平均单次延迟: {sum(latencies)/len(latencies):.2f}s | 吞吐约 {len(latencies)/sum(latencies):.2f} req/s")
print("注: 生产服务用 TGI/vLLM 可做 batch + 流式，延迟与吞吐远优于单条串行。")
""")

# ---------------- M07 ----------------
md("""## M07 · Model Memory / VRAM 显存
显存 = 权重 + KV cache + 激活。
- 权重：参数量 × dtype 字节（bf16/fp16=2B，fp32=4B）
- KV cache：2(K,V) × 层数 × kv_heads × d_head × 序列长 × 2B
- 激活：前向中间结果，随 batch/序列长变化

下面既用公式估算，也在 GPU 上**实测** `memory_allocated`。
""")
code("""cfg = model.config
total_params = sum(p.numel() for p in model.parameters())

w_bytes = total_params * 2                       # bf16/fp16
n_layers = cfg.num_hidden_layers
n_kv = getattr(cfg, "num_key_value_heads", cfg.num_attention_heads)
d_head = cfg.hidden_size // cfg.num_attention_heads
seq = 2048
kv_bytes = 2 * n_layers * n_kv * d_head * seq * 2

print(f"权重显存(bf16)     : {w_bytes/1e9:.2f} GB")
print(f"KV cache({seq} tok): {kv_bytes/1e6:.1f} MB")
print(f"   公式 = 2 * {n_layers}层 * {n_kv} kv_heads * {d_head} d_head * {seq} * 2B")

if device == "cuda":
    torch.cuda.empty_cache()
    mem = torch.cuda.memory_allocated() / 1e9
    print(f"\\n实测已分配显存(加载后): {mem:.2f} GB")
""")

# ---------------- M08 ----------------
md("""## M08 · Quantization 量化
4-bit 量化：把权重从 16-bit 压缩到 4-bit（线性缩放 + 零点），显存降约 4×、磁盘降约 4×，精度略损。
Colab 是 CUDA，用 `load_in_4bit`（bitsandbytes）即可真跑；**Mac 本地无 CUDA，量化走 GGUF + llama.cpp**。
""")
code("""from transformers import BitsAndBytesConfig

bq = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype="bfloat16")
model4 = AutoModelForCausalLM.from_pretrained(MODEL_ID, quantization_config=bq, device_map="auto")

tot4 = sum(p.numel() for p in model4.parameters())
print("fp16 参数量 :", f"{total_params:,}")
print("4bit 参数量 :", f"{tot4:,}", "(逻辑参数不变，存储压到 4bit)")
print(f"4bit 权重估算: {tot4*0.5/1e9:.2f} GB  (vs fp16 {w_bytes/1e9:.2f} GB)")

inp = tok("量子计算的优势是", return_tensors="pt").to(device)
o4 = model4.generate(**inp, max_new_tokens=30, do_sample=False)
print("\\n4bit 生成:", tok.decode(o4[0], skip_special_tokens=True))
print("\\n注: Mac 本地量化路线 = GGUF(q4_0/q4_k_m) + llama.cpp，无需 CUDA。")
""")

# ---------------- M09 ----------------
md("""## M09 · Open Source LLM Application 应用
把 M01–M08 串成一个迷你聊天应用：带历史记忆、可调 temperature/top_p、复用 chat template。
""")
code("""def chat(user_msg, history=None, max_new=80, temperature=0.8, top_p=0.9):
    messages = (history or []) + [{"role": "user", "content": user_msg}]
    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(prompt, return_tensors="pt").to(device)
    out = model.generate(**inputs, max_new_tokens=max_new,
                         do_sample=temperature > 0, temperature=temperature, top_p=top_p)
    resp = tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    return resp

print("=== 迷你聊天应用演示 ===")
demo = ["你是谁？",
        "用三句话介绍 Transformer。",
        "那它相比 RNN 有什么优势？"]
history = []
for q in demo:
    a = chat(q, history)
    history.append({"role": "user", "content": q})
    history.append({"role": "assistant", "content": a})
    print(f"用户: {q}\\n助手: {a}\\n")

print("=== P07 全部 Milestone 已在本 notebook 真实跑通 ===")
""")

# ---------------- 写出 ipynb ----------------
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "accelerator": "GPU",
        "colab": {"provenance": [], "gpuType": "T4"},
    },
    "nbformat": 4,
    "nbformat_minor": 0,
}

out_path = os.path.join(os.path.dirname(__file__), "p07_colab.ipynb")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"written: {out_path}")
print(f"cells  : {len(cells)} (markdown={sum(1 for c in cells if c['cell_type']=='markdown')}, code={sum(1 for c in cells if c['cell_type']=='code')})")
