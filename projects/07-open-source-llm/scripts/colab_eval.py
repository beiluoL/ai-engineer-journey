"""Colab 侧脚本：用同一组「训练集未见过」的问题，对比微调前/后的回答。

用法：
    python colab_eval.py before   # 评测基座模型 ./models/qwen2.5-1.5b
    python colab_eval.py after    # 评测合并后的模型 ./models/qwen2.5-1.5b-java-interview-merged

在 LLaMA-Factory 目录内运行。
"""
import sys

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

mode = sys.argv[1] if len(sys.argv) > 1 else "before"
if mode == "after":
    MODEL_DIR = "./models/qwen2.5-1.5b-java-interview-merged"
    tag = "微调后"
else:
    MODEL_DIR = "./models/qwen2.5-1.5b"
    tag = "微调前"

print(f"===== 评测模式：{tag} | 模型：{MODEL_DIR} =====")
tok = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR, torch_dtype="auto", device_map="auto"
)

# 三道「训练集里没有」的延伸问题，用于检验泛化与幻觉。
questions = [
    "请解释 volatile 能保证原子性吗？",
    "ConcurrentHashMap 在 JDK 8 中如何保证线程安全？",
    "为什么 HashMap 的容量通常是 2 的幂？",
]

for q in questions:
    messages = [{"role": "user", "content": q}]
    text = tok.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tok(text, return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=200)
    ans = tok.decode(
        out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
    )
    print(f"Q: {q}")
    print(f"A({tag}): {ans}")
    print("-" * 40)
