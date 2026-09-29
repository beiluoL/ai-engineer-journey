"""``ft.trainer`` —— 只训练 adapter 的训练器。

这里的三条主线：
1. **优化器里只有 adapter**（多一个基座参数进来就是 bug）。
2. **loss 真的下降**（训练器写了但 loss 不动 = 梯度没接上）。
3. **基座字节级不动**（冻结必须是真的，不是"我以为冻住了"）。
"""

from __future__ import annotations

import numpy as np
import pytest

from ft import (
    LoRATrainer,
    base_parameters,
    count_parameters,
    curve_summary,
    inject_lora,
    named_parameters,
    trainable_parameters,
)


def test_only_adapter_params_enter_optimizer(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3)
    assert len(trainer.params) == 26
    assert all(p.requires_grad for p in trainer.params)


def test_optimizer_params_are_exactly_the_adapter_tensors(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3)
    trainable_ids = {id(p) for p in trainable_parameters(fresh_model)}
    assert {id(p) for p in trainer.params} == trainable_ids


def test_no_base_param_in_optimizer(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3)
    base_ids = {id(p) for _p, p in base_parameters(fresh_model)}
    assert not ({id(p) for p in trainer.params} & base_ids)


def test_trainer_without_lora_raises(fresh_model):
    with pytest.raises(ValueError):
        LoRATrainer(fresh_model, lr=1e-3)


def test_loss_decreases(fresh_model, sft_examples):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    losses = trainer.run(sft_examples, 30, batch_size=4)
    s = curve_summary(losses)
    assert s["last_window"] < s["first_window"]
    assert s["drop"] > 0.5


def test_base_weights_unchanged_bytewise(fresh_model, sft_examples):
    """训练后基座权重必须**字节级**不变。"""
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    snapshot = {p: param.data.tobytes() for p, param in base_parameters(fresh_model)}
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 20, batch_size=4)
    for p, param in base_parameters(fresh_model):
        assert param.data.tobytes() == snapshot[p], f"基座参数被动了：{p}"


def test_adapter_weights_actually_change(fresh_model, sft_examples):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    snapshot = [p.data.tobytes() for p in trainable_parameters(fresh_model)]
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 10, batch_size=4)
    after = [p.data.tobytes() for p in trainable_parameters(fresh_model)]
    assert sum(a != b for a, b in zip(snapshot, after)) == 26


def test_step_counter_advances(fresh_model, sft_examples):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    trainer.run(sft_examples, 7, batch_size=4)
    trainer.run(sft_examples, 5, batch_size=4)
    assert trainer.step == 12
    assert len(trainer.losses) == 12


def test_determinism_same_seed(fresh_model, sft_examples):
    """同 seed 跑两遍，loss 曲线必须一致。"""
    inject_lora(fresh_model, r=4, alpha=8.0, rng=0)
    t1 = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    l1 = t1.run(sft_examples, 12, batch_size=4)

    fresh2 = fresh_model
    from ft import ensure_base_model

    m2, _, _ = ensure_base_model()
    inject_lora(m2, r=4, alpha=8.0, rng=0)
    t2 = LoRATrainer(m2, lr=3e-3, seed=0)
    l2 = t2.run(sft_examples, 12, batch_size=4)
    assert np.allclose(l1, l2, atol=1e-10)
    assert fresh2 is not None


def test_determinism_same_seed_same_model(fresh_model, sft_examples):
    """同一份模型、同 seed 两次独立初始化训练器 → 前若干步一致。"""
    inject_lora(fresh_model, r=4, alpha=8.0, rng=0)
    t1 = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    l1 = t1.run(sft_examples, 10, batch_size=4)
    m2, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m2, r=4, alpha=8.0, rng=0)
    t2 = LoRATrainer(m2, lr=3e-3, seed=0)
    l2 = t2.run(sft_examples, 10, batch_size=4)
    assert np.allclose(l1, l2, atol=1e-10)


def test_different_seed_gives_different_order(fresh_model, sft_examples):
    inject_lora(fresh_model, r=4, alpha=8.0, rng=0)
    t1 = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    l1 = t1.run(sft_examples, 12, batch_size=4)
    m2, _, _ = __import__("ft").ensure_base_model()
    inject_lora(m2, r=4, alpha=8.0, rng=0)
    t2 = LoRATrainer(m2, lr=3e-3, seed=123)
    l2 = t2.run(sft_examples, 12, batch_size=4)
    assert not np.allclose(l1, l2)


def test_batches_cover_all_examples_each_epoch(fresh_model, sft_examples):
    """一个 epoch 内每个样本恰好被用一次（不重不漏）。"""
    trainer = LoRATrainer.__new__(LoRATrainer)
    trainer.seed = 0
    trainer._perm_cache = {}
    batches = trainer._epoch_batches(len(sft_examples), 4, 0)
    seen = np.concatenate(batches)
    assert len(seen) == len(sft_examples)
    assert set(seen.tolist()) == set(range(len(sft_examples)))


def test_epoch_permutation_is_deterministic(fresh_model, sft_examples):
    trainer = LoRATrainer.__new__(LoRATrainer)
    trainer.seed = 0
    trainer._perm_cache = {}
    a = trainer._epoch_batches(59, 4, 3)
    trainer2 = LoRATrainer.__new__(LoRATrainer)
    trainer2.seed = 0
    trainer2._perm_cache = {}
    b = trainer2._epoch_batches(59, 4, 3)
    assert all(np.array_equal(x, y) for x, y in zip(a, b))


def test_sgd_also_works(fresh_model, sft_examples):
    """训练器不绑定 Adam：换成 SGD 也能把 adapter 训下去。

    两点必须写对，否则这条会假失败：

    1. **SGD 的学习率要比 Adam 大一个量级**。Adam 会把梯度按二阶矩归一，
       等效步长与梯度量级无关；SGD 是裸的 ``w -= lr*g``，而 LoRA 里 B 初始为
       零、梯度很小，lr=1e-2 时实测 30 步只掉 0.26（8.25→8.00），换成 3e-2
       掉 1.41（8.20→6.79）。
    2. **不能拿「首步 vs 末步」单步 loss 比**。batch_size=4、59 条异质样本，
       单步 loss 的批次间抖动有 0.9 那么大（min 7.37 / 末步 8.32），末步恰好
       抽到难批次就会把断言打穿。这里比的是首尾各 10 步的**窗口均值**。
    """
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-2, optimizer="sgd", seed=0)
    losses = trainer.run(sft_examples, 30, batch_size=4)
    s = curve_summary(losses)
    assert s["last_window"] < s["first_window"]
    assert s["drop"] > 0.5
    assert s["best"] < s["first"] - 1.0


def test_curve_summary_fields(fresh_model, sft_examples):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    trainer = LoRATrainer(fresh_model, lr=3e-3, seed=0)
    losses = trainer.run(sft_examples, 20, batch_size=4)
    s = curve_summary(losses)
    assert s["n_steps"] == 20
    assert s["first"] == losses[0] and s["last"] == losses[-1]
    assert s["best"] == min(losses)


def test_curve_summary_empty():
    s = curve_summary([])
    assert np.isnan(s["first"])


def test_full_finetune_changes_base(fresh_model, sft_examples):
    """对照组：全量微调**会**改基座（LoRA 不会）—— 证明上面的冻结断言不是恒真的。"""
    snapshot = {p: param.data.tobytes() for p, param in named_parameters(fresh_model)}
    from ft.sft_data import pad_batch
    from model import Adam, cross_entropy

    params = [p for _p, p in named_parameters(fresh_model)]
    opt = Adam(params, lr=3e-3)
    n_batches = max(1, int(np.ceil(len(sft_examples) / 4)))
    for step in range(10):
        epoch, bi = divmod(step, n_batches)
        rng = np.random.default_rng(epoch)
        idx = rng.permutation(len(sft_examples))
        sel = idx[bi * 4 : bi * 4 + 4]
        X, Y, M = pad_batch([sft_examples[int(i)] for i in sel])
        loss = cross_entropy(fresh_model(X, mask=None), Y, mask=M)
        loss.backward()
        opt.step()
    changed = sum(1 for p, param in named_parameters(fresh_model)
                  if param.data.tobytes() != snapshot[p])
    assert changed > 20


def test_trainable_ratio_after_injection(fresh_model):
    inject_lora(fresh_model, r=8, alpha=16.0, rng=0)
    counts = count_parameters(fresh_model)
    assert 0.05 < counts["trainable_ratio"] < 0.20
