"""优化三本账（M09）：量化体积/精度、KV Cache 账本、部署体积。"""

from __future__ import annotations

from tiny.optimize import (
    deployment_size_table,
    granularity_report,
    kv_cache_report,
    quantization_report,
)
from tiny.model import parameter_report


def test_quantization_compresses_and_measures_cost(trained_bundle):
    cfg = trained_bundle["cfg"]
    model = trained_bundle["model"]
    examples = trained_bundle["dataset"].val_examples
    report = quantization_report(cfg, model, examples, bits_list=(8, 4))
    for name in ("INT8", "INT4", "NF4"):
        item = report["quantizers"][name]
        assert item["compression_ratio"] > 1.0
        assert item["storage_bytes"] < item["fp32_bytes"]
        assert item["ppl_after"] > 0
    # 位宽越低压缩比越高 —— 这条不变量能挡住「量化写反了」这类错误
    assert report["quantizers"]["INT4"]["compression_ratio"] > report["quantizers"]["INT8"]["compression_ratio"]


def test_int8_costs_less_than_int4_on_tiny_model(trained_bundle):
    """实测反直觉：小模型上 INT4 的困惑度代价大于 INT8。"""
    cfg = trained_bundle["cfg"]
    report = quantization_report(cfg, trained_bundle["model"],
                                 trained_bundle["dataset"].val_examples, bits_list=(8, 4))
    int8 = abs(report["quantizers"]["INT8"]["ppl_delta_pct"])
    int4 = abs(report["quantizers"]["INT4"]["ppl_delta_pct"])
    assert int4 > int8


def test_kv_cache_report_has_architecture_numbers(cfg, trained_bundle):
    params = parameter_report(trained_bundle["model"])
    report = kv_cache_report(cfg, trained_bundle["model"], params["total"])
    arch = report["architecture"]
    assert arch["layers"] == cfg.model.n_layers
    assert arch["head_dim"] == cfg.model.d_model // cfg.model.n_heads
    expected = 2 * arch["layers"] * arch["kv_heads"] * arch["head_dim"] * 4
    assert report["bytes_per_token_fp32"] == expected
    assert report["seq_len_to_exceed_weights"] > 0
    assert len(report["table"]) == 8  # 4 个长度 × 2 个 batch


def test_deployment_size_shrinks_with_precision(trained_bundle):
    params = parameter_report(trained_bundle["model"])
    rows = deployment_size_table(trained_bundle["model"], params["total"])
    sizes = [row["bytes"] for row in rows]
    assert sizes == sorted(sizes, reverse=True)
    assert rows[-1]["precision"].startswith("INT4")


def test_granularity_report_prefers_per_channel(trained_bundle):
    report = granularity_report(trained_bundle["model"])
    assert report["shape"]
    for kind in ("INT8", "INT4"):
        assert (
            report["per_channel"][kind]["relative_l2"]
            <= report["per_tensor"][kind]["relative_l2"] + 1e-12
        )
