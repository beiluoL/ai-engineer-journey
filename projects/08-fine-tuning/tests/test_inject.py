"""``ft.inject`` —— 把 LoRA 塞进 P06 的 TransformerLM，以及「冻结」到底冻结了什么。"""

from __future__ import annotations

import numpy as np
import pytest

from ft import (
    DEFAULT_TARGETS,
    base_parameters,
    count_parameters,
    enable_deterministic_autograd,
    freeze_base,
    inject_lora,
    iter_targets,
    lora_layers,
    named_parameters,
    ordered_prev,
    trainable_parameters,
)


def test_iter_targets_finds_exactly_13_layers(fresh_model):
    """默认注入点是 13 个线性层：2×(Wq,Wk,Wv,Wo,W1,W2) + proj。"""
    hits = iter_targets(fresh_model)
    assert len(hits) == 13
    leaves = [p.split(".")[-1] for p, _parent, _key, _param in hits]
    assert sorted(set(leaves)) == sorted(set(DEFAULT_TARGETS))


def test_inject_replaces_all_targets(fresh_model):
    injected = inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    assert len(injected) == 13
    assert len(lora_layers(fresh_model)) == 13


def test_inject_preserves_weight_values(fresh_model):
    """注入不能改动基座权重的值 —— 只是把它包进 LoRA 层里。"""
    before = {p: param.data.copy() for p, param in named_parameters(fresh_model)}
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    after = {p: param.data.copy() for p, param in base_parameters(fresh_model)}
    assert set(before) == set(after)
    for p in before:
        assert np.array_equal(before[p], after[p])


def test_base_parameter_count_is_stable_across_injection(fresh_model):
    """注入前后「基座参数量」必须一模一样。"""
    before = count_parameters(fresh_model)
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    after = count_parameters(fresh_model)
    assert before["total"] == after["base"]


@pytest.mark.parametrize("r", [1, 2, 4, 8, 16])
def test_adapter_size_matches_formula(fresh_model, r):
    inject_lora(fresh_model, r=r, alpha=float(2 * r), rng=0)
    counts = count_parameters(fresh_model)
    expected = sum(r * (l.in_features + l.out_features) for _p, l in lora_layers(fresh_model))
    assert counts["trainable"] == expected


def test_trainable_parameters_count(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    params = trainable_parameters(fresh_model)
    assert len(params) == 26  # 13 层 × 2
    assert all(p.requires_grad for p in params)


def test_freeze_base_sets_requires_grad_false(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    frozen = freeze_base(fresh_model)
    assert frozen == 28  # 13 个 W + 4 个 FFN bias + 10 个 LayerNorm + 1 个 embedding
    base = [p for _p, p in base_parameters(fresh_model)]
    assert all(not p.requires_grad for p in base)
    assert all(p.requires_grad for p in trainable_parameters(fresh_model))


def test_p06_parameters_misses_token_embedding(fresh_model):
    """一个实测发现：P06 的 parameters() 漏掉了 TokenEmbedding（它不是 Module 子类）。"""
    counts = count_parameters(fresh_model)
    assert counts["p06_elements"] < counts["total"]
    assert counts["total"] - counts["p06_elements"] == fresh_model.token_emb.weight.data.size


def test_named_parameters_includes_embedding(fresh_model):
    paths = [p for p, _ in named_parameters(fresh_model)]
    assert "token_emb.weight" in paths


def test_injection_does_not_change_model_output(fresh_model):
    """B=0 ⟹ 注入前后整机输出逐位相同。"""
    ids = np.random.randint(4, 1000, (2, 32))
    before = fresh_model(ids, mask=None).data.copy()
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    after = fresh_model(ids, mask=None).data
    assert np.array_equal(before, after)


def test_qlora_injection(fresh_model):
    from ft import QLoRALinear

    injected = inject_lora(fresh_model, r=4, alpha=8.0, kind="qlora", rng=0)
    assert len(injected) == 13
    assert all(isinstance(l, QLoRALinear) for _p, l in injected)
    assert len(trainable_parameters(fresh_model)) == 26


def test_inject_unknown_kind_raises(fresh_model):
    with pytest.raises(ValueError):
        inject_lora(fresh_model, kind="nope")


def test_inject_wrong_target_raises(fresh_model):
    with pytest.raises(RuntimeError):
        inject_lora(fresh_model, targets=("no_such_layer",))


def test_narrow_target_injection(fresh_model):
    """只注入 Q/V 投影时层数应为 4（2 层 × 2）。"""
    injected = inject_lora(fresh_model, targets=("Wq", "Wv"), r=4, alpha=8.0, rng=0)
    assert len(injected) == 4


# ---------------------------------------------------------------- 可复现性
# 这几条守护的是「同一份代码换个进程跑，数字不变」。P06 的 Tensor._prev 是 set，
# 遍历顺序依赖对象地址；P08 用 ft.paths 里的补丁把它换成按创建顺序排列的 list。


def test_tensor_prev_is_ordered_list():
    from model import Tensor

    a = Tensor(np.zeros(2))
    b = Tensor(np.zeros(2))
    c = Tensor(np.zeros(2), _children=(a, b))
    assert isinstance(c._prev, list)
    assert [t._seq for t in c._prev] == [a._seq, b._seq]


def test_ordered_prev_follows_creation_order():
    from model import Tensor

    nodes = [Tensor(np.zeros(2)) for _ in range(5)]
    shuffled = [nodes[3], nodes[0], nodes[4], nodes[2], nodes[1]]
    assert [id(t) for t in ordered_prev(shuffled)] == [id(t) for t in nodes]


def test_enable_deterministic_autograd_is_idempotent():
    """import ft 时已经打过一次，再调用必须返回 False 而不是重复包一层。"""
    assert enable_deterministic_autograd() is False


def test_walk_parameters_ignores_autograd_edges(fresh_model):
    """``_prev`` 是计算图的边，不能被当成参数收集进来。"""
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    paths = [p for p, _ in named_parameters(fresh_model)]
    assert not any("_prev" in p for p in paths)
    assert len(paths) == 54  # 28 个基座张量（含 13 个 .W）+ 13×2 个 A/B
