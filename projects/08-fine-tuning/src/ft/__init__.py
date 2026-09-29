"""Project 08 —— ft 包：从零手写的 LoRA / QLoRA 微调流水线。

    from ft import (
        # 基座（复用 P06）
        ensure_base_model, build_base_model, build_tokenizer,
        # LoRA / QLoRA
        LoRALinear, QLoRALinear, LoRAConfig, inject_lora, freeze_base,
        quantize_nf4, dequantize_nf4, memory_ledger, training_memory,
        # 数据 / 训练 / 断点 / 合并 / 评估
        build_sft_examples, LoRATrainer, save_checkpoint, load_checkpoint,
        merge_lora, perplexity, forgetting_report,
    )

整套代码只有 numpy，没有 torch / peft / transformers —— 每个数字都是真跑出来的。
"""

from __future__ import annotations

from .paths import (  # noqa: F401
    JAVA_INTERVIEW_JSON,
    P06_SRC,
    P08_MODELS,
    P08_ROOT,
    enable_deterministic_autograd,
    ensure_dir,
    ensure_p06_importable,
    ensure_p07_dataset,
    ordered_prev,
)

from .base import (  # noqa: F401
    DEFAULT_CONFIG,
    ModelConfig,
    build_base_model,
    build_tokenizer,
    ensure_base_model,
    general_corpus,
    load_base_model,
    pretrain_model,
    save_base_model,
)
from .checkpoint import (  # noqa: F401
    adapter_report,
    load_adapter,
    load_checkpoint,
    save_adapter,
    save_checkpoint,
)
from .eval import (  # noqa: F401
    compare,
    evaluate,
    forgetting_report,
    generate_text,
    perplexity,
)
from .inject import (  # noqa: F401
    DEFAULT_TARGETS,
    base_parameters,
    count_parameters,
    freeze_base,
    inject_lora,
    iter_targets,
    lora_layers,
    named_parameters,
    trainable_parameters,
    walk_parameters,
)
from .lora import LoRAConfig, LoRALinear  # noqa: F401
from .merge import (  # noqa: F401
    lora_overhead_report,
    max_abs_diff,
    merge_lora,
    time_forward,
    unmerge_lora,
)
from .qlora import (  # noqa: F401
    QLoRALinear,
    human_bytes,
    memory_ledger,
    training_memory,
)
from .quantize import (  # noqa: F401
    NF4_LEVELS,
    NF4Tensor,
    dequantize_nf4,
    nf4_codebook,
    nf4_storage_bytes,
    quantization_error,
    quantize_nf4,
)
from .sft_data import (  # noqa: F401
    SFTExample,
    build_lm_examples,
    build_sft_examples,
    dataset_stats,
    load_java_records,
    pad_batch,
    render_example,
    visualize_example,
)
from .trainer import LoRATrainer, curve_summary  # noqa: F401

__all__ = [
    "DEFAULT_CONFIG",
    "DEFAULT_TARGETS",
    "JAVA_INTERVIEW_JSON",
    "LoRAConfig",
    "LoRALinear",
    "LoRATrainer",
    "ModelConfig",
    "NF4_LEVELS",
    "NF4Tensor",
    "P06_SRC",
    "P08_MODELS",
    "P08_ROOT",
    "QLoRALinear",
    "SFTExample",
    "adapter_report",
    "base_parameters",
    "build_base_model",
    "build_lm_examples",
    "build_sft_examples",
    "build_tokenizer",
    "compare",
    "count_parameters",
    "curve_summary",
    "dataset_stats",
    "dequantize_nf4",
    "ensure_base_model",
    "ensure_dir",
    "ensure_p06_importable",
    "ensure_p07_dataset",
    "enable_deterministic_autograd",
    "evaluate",
    "forgetting_report",
    "freeze_base",
    "general_corpus",
    "generate_text",
    "human_bytes",
    "inject_lora",
    "iter_targets",
    "load_adapter",
    "load_base_model",
    "load_checkpoint",
    "load_java_records",
    "lora_layers",
    "lora_overhead_report",
    "max_abs_diff",
    "memory_ledger",
    "merge_lora",
    "named_parameters",
    "nf4_codebook",
    "nf4_storage_bytes",
    "ordered_prev",
    "pad_batch",
    "perplexity",
    "pretrain_model",
    "quantization_error",
    "quantize_nf4",
    "render_example",
    "save_adapter",
    "save_base_model",
    "save_checkpoint",
    "time_forward",
    "trainable_parameters",
    "training_memory",
    "unmerge_lora",
    "visualize_example",
    "walk_parameters",
]
