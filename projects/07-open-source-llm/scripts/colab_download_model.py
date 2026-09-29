"""Colab 侧脚本：把 Qwen2.5-1.5B-Instruct 基座模型下载到 ./models/qwen2.5-1.5b。

在 LLaMA-Factory 目录内运行（notebook 已 %cd 过去）。
"""
import os

from huggingface_hub import snapshot_download

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
MODEL_DIR = "./models/qwen2.5-1.5b"

os.makedirs(MODEL_DIR, exist_ok=True)
snapshot_download(MODEL_ID, local_dir=MODEL_DIR)
print("基座模型已下载到", MODEL_DIR)
