"""端到端 Pipeline（M11）：一条命令跑完全链路，缓存与分阶段重跑都可用。"""

from __future__ import annotations

import json

import tiny.pipeline as pipeline_mod
from tiny import default_config, run_pipeline


def _artifact(name: str):
    """取**当前**的产物路径（会被 ``tmp_models_dir`` 重定向，不能 import 成常量）。"""
    return getattr(pipeline_mod, name)


def test_pipeline_runs_end_to_end(monkeypatch, tmp_models_dir):
    """完整链路：config → tokenizer → dataset → model → train → evaluate → optimize。"""
    cfg = default_config()
    cfg.tokenizer.kind = "char"
    cfg.tokenizer.vocab_size = 1280
    cfg.model.d_model = 32
    cfg.model.d_ff = 64
    cfg.model.n_layers = 1
    cfg.model.max_len = 32
    cfg.data.stride = 16
    cfg.optim.lr = 3e-3
    cfg.optim.warmup_steps = 5
    cfg.train.n_steps = 20
    cfg.train.eval_every = 10
    cfg.train.patience = 0
    cfg.train.log_every = 0
    cfg.gen.max_new_tokens = 8

    result = run_pipeline(cfg, force=True, verbose=False, do_serve=False)
    assert result.tokenizer is not None and result.model is not None
    assert result.train_report["last_loss"] < result.train_report["first_loss"]
    assert result.eval_report["perplexity"] > 0
    assert "quantizers" in result.opt_report["quantization"]
    assert _artifact("REPORT_JSON").is_file()

    payload = json.loads(_artifact("REPORT_JSON").read_text(encoding="utf-8"))
    assert payload["config"]["model"]["d_model"] == 32
    assert "train" in payload and "evaluate" in payload


def test_pipeline_reuses_cached_artifacts(tmp_models_dir):
    """第二次跑必须复用分词器与模型缓存（否则跨章节的数字对不上）。"""
    cfg = default_config()
    cfg.tokenizer.kind = "char"
    cfg.model.d_model = 32
    cfg.model.d_ff = 64
    cfg.model.n_layers = 1
    cfg.model.max_len = 32
    cfg.data.stride = 16
    cfg.optim.warmup_steps = 2
    cfg.train.n_steps = 5
    cfg.train.eval_every = 5
    cfg.train.patience = 0
    cfg.train.log_every = 0

    first = run_pipeline(cfg, force=True, verbose=False, do_serve=False)
    second = run_pipeline(cfg, force=False, verbose=False, do_serve=False)
    assert first.cached["tokenizer"] is False
    assert second.cached["tokenizer"] is True
    assert second.cached["model"] is True
    assert second.train_report["reused_checkpoint"] is True


def test_pipeline_can_run_single_stage(tmp_models_dir):
    cfg = default_config()
    result = run_pipeline(cfg, verbose=False, do_serve=False, only=["config", "tokenizer"])
    assert result.tokenizer is not None
    assert result.model is None  # 没跑到模型阶段
    assert _artifact("CONFIG_JSON").is_file()
