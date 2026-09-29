"""Colab 侧脚本：准备 Java 面试数据集 + LLaMA-Factory 注册 + 写出训练/合并配置。

在 LLaMA-Factory 目录内运行（notebook 已 %cd 过去）。
数据集从本仓库 GitHub raw 拉取，保证与仓库一致。
"""
import json
import os
import urllib.request

REPO_BASE = "https://raw.githubusercontent.com/beiluoL/ai-engineer-journey/main/projects/07-open-source-llm"

# 1) 拉取数据集
os.makedirs("data", exist_ok=True)
with urllib.request.urlopen(f"{REPO_BASE}/data/java_interview.json", timeout=30) as r:
    data = json.loads(r.read())
print("数据集条数:", len(data))
with open("data/java_interview.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 2) 注册到 LLaMA-Factory（alpaca 格式：instruction/input/output）
reg = {
    "java_interview": {
        "file_name": "java_interview.json",
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output",
        },
    }
}
with open("data/dataset_info.json", "w", encoding="utf-8") as f:
    json.dump(reg, f, ensure_ascii=False, indent=2)
print("已写入 data/java_interview.json 与 data/dataset_info.json")

# 3) QLoRA SFT 训练配置
train_yaml = """### model
model_name_or_path: ./models/qwen2.5-1.5b

### method
stage: sft
do_train: true
finetuning_type: lora
lora_rank: 8
lora_alpha: 16
lora_target: all
quantization_bit: 4

### dataset
dataset: java_interview
cutoff_len: 1024
max_samples: 1000
overwrite_cache: true
preprocessing_num_workers: 16

### output
output_dir: saves/qwen2.5-1.5b/lora/java-interview
logging_steps: 10
save_steps: 100
plot_loss: true
overwrite_output_dir: true

### train
per_device_train_batch_size: 1
gradient_accumulation_steps: 8
learning_rate: 2.0e-4
num_train_epochs: 3.0
lr_scheduler_type: cosine
warmup_ratio: 0.1
bf16: true

### eval
val_size: 0.1
eval_strategy: steps
eval_steps: 50
"""
os.makedirs("examples/train_lora", exist_ok=True)
with open("examples/train_lora/qwen_qlora_java.yaml", "w") as f:
    f.write(train_yaml)
print("已写入 examples/train_lora/qwen_qlora_java.yaml")

# 4) LoRA 合并（导出）配置
export_yaml = """### model
model_name_or_path: ./models/qwen2.5-1.5b
adapter_name_or_path: saves/qwen2.5-1.5b/lora/java-interview

### export
export_dir: models/qwen2.5-1.5b-java-interview-merged
export_size: 2
export_device: cpu
"""
os.makedirs("examples/merge_lora", exist_ok=True)
with open("examples/merge_lora/qwen_java_export.yaml", "w") as f:
    f.write(export_yaml)
print("已写入 examples/merge_lora/qwen_java_export.yaml")
