"""Project 09：纯 numpy 的 LLM 评估、推理与服务组件。"""

from .paths import ensure_deps_importable

ensure_deps_importable()

from .autoeval import AutoEvalScore, aggregate_scores, evaluate_answer, rank_answers
from .batching import Request, compare_batching, simulate_continuous, simulate_static
from .benchmark import Benchmark, BenchmarkTask, tasks_from_records
from .compare import evaluate_models, paired_compare, summarize
from .engine import CausalLMWithKVCache, KVCacheState
from .evalset import EvalSplit, build_evaluation_set, leakage_report, normalize_instruction
from .kvbook import KVArchitecture, bytes_per_token, kv_cache_bytes
from .metrics import (
    answer_coverage,
    answer_perplexity,
    calibration,
    evaluate,
    expected_calibration_error,
    perplexity,
    reliability_bins,
    token_accuracy,
)
from .paged import PagedKVCache, memory_comparison
from .quantize import QuantizedTensor, quantize_int4, quantize_int8, quantize_model

__all__ = [
    "AutoEvalScore", "Benchmark", "BenchmarkTask", "CausalLMWithKVCache", "EvalSplit",
    "KVArchitecture", "KVCacheState", "PagedKVCache", "QuantizedTensor", "Request",
    "aggregate_scores", "answer_coverage", "answer_perplexity", "build_evaluation_set",
    "bytes_per_token", "calibration", "compare_batching", "ensure_deps_importable",
    "evaluate", "evaluate_answer", "evaluate_models", "expected_calibration_error",
    "kv_cache_bytes", "leakage_report", "memory_comparison", "normalize_instruction",
    "paired_compare", "perplexity", "quantize_int4", "quantize_int8", "quantize_model",
    "rank_answers", "reliability_bins", "simulate_continuous", "simulate_static",
    "summarize", "tasks_from_records", "token_accuracy",
]
