"""Project 10 —— Tiny LLM / AI Engineer Capstone。

一句话定位：**把 Project 01–09 的能力重新串成一条可复现的 LLM 工程链路**。

    from tiny import default_config, run_pipeline

    result = run_pipeline()          # 一条命令跑完全链路
    result.eval_report["perplexity"]  # 拿数字

分层（每一层都对应一个 Milestone）：

    config     配置契约（唯一入口，可校验 / 可落盘）
    tok        分词器（BPE，复用 P06）
    data       数据集（清洗 / 切分 / 无泄漏 / 滑窗打包）
    model      模型装配 + 参数账 + 因果性自检（复用 P06 的 Transformer）
    train      训练 Pipeline（调度 / 裁剪 / 早停 / 检查点 / 续训）
    evaluate   三层评估（语言层 / 校准层 / 生成层，复用 P09 指标）
    infer      推理与采样（temperature / top-k / top-p / KV Cache / 流式）
    optimize   优化（INT8 / INT4 / NF4 量化 + KV Cache 账本，复用 P09）
    serve      服务化（OpenAI 兼容 HTTP + SSE + 压测，复用 P09）
    pipeline   端到端编排（缓存 / 可重跑 / 报告落盘）

**刻意不重写**：Tokenizer 与 Transformer 用 P06 的手写实现（含从零 autograd），
确定性补丁用 P08 的，评估与推理组件用 P09 的。P10 的价值在**串联与工程化**，
不在重复造轮子 —— 这也正是 Capstone 要证明的能力。
"""

from __future__ import annotations

from . import config, data, evaluate, infer, model, optimize, paths, pipeline, serve, tok, train
from .config import (
    DataConfig,
    GenConfig,
    ModelConfig,
    OptimConfig,
    ServeConfig,
    TinyConfig,
    TokenizerConfig,
    TrainConfig,
    default_config,
    load_config,
    save_config,
)
from .data import Dataset, build_dataset, load_corpus, make_examples, pad_batch, split_lines
from .evaluate import compare_models, evaluate_model, qa_pairs_from_lines
from .infer import Generator
from .model import build_model, build_optimizer, forward_sanity, parameter_report, set_seed
from .optimize import kv_cache_report, optimization_report, quantization_report
from .pipeline import run_pipeline
from .serve import build_engine, load_test, serve_model, smoke_test
from .tok import build_tokenizer, load_tokenizer, save_tokenizer, tokenizer_stats
from .train import LMTrainer, evaluate_loss, load_checkpoint, save_checkpoint

__version__ = "0.1.0"

__all__ = [
    # 子模块
    "config", "data", "evaluate", "infer", "model", "optimize", "paths", "pipeline",
    "serve", "tok", "train",
    # 配置
    "DataConfig", "GenConfig", "ModelConfig", "OptimConfig", "ServeConfig", "TinyConfig",
    "TokenizerConfig", "TrainConfig", "default_config", "load_config", "save_config",
    # 数据 / 分词
    "Dataset", "build_dataset", "build_tokenizer", "load_corpus", "load_tokenizer",
    "make_examples", "pad_batch", "save_tokenizer", "split_lines", "tokenizer_stats",
    # 模型 / 训练
    "build_model", "build_optimizer", "evaluate_loss", "forward_sanity", "LMTrainer",
    "load_checkpoint", "parameter_report", "save_checkpoint", "set_seed",
    # 评估 / 推理 / 优化 / 服务
    "compare_models", "evaluate_model", "Generator", "kv_cache_report", "optimization_report",
    "quantization_report", "build_engine", "load_test", "serve_model", "smoke_test",
    "qa_pairs_from_lines",
    # 端到端
    "run_pipeline", "__version__",
]
