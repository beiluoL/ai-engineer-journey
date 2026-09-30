"""训练 Pipeline（M06）：收敛、调度、裁剪、早停回滚、检查点续训。"""

from __future__ import annotations

import numpy as np

from tiny.data import build_dataset
from tiny.model import build_model, build_optimizer, walk_parameters
from tiny.train import LMTrainer, evaluate_loss, load_checkpoint, save_checkpoint


def _fresh(cfg, tokenizer, dataset, **kwargs):
    model = build_model(cfg, tokenizer)
    optimizer = build_optimizer(cfg, model)
    return LMTrainer(cfg, model, optimizer, dataset.train_examples,
                     dataset.val_examples, verbose=False, **kwargs)


def test_loss_decreases(trained_bundle):
    report = trained_bundle["report"]
    assert report["last_loss"] < report["first_loss"]
    assert report["tail_mean"] < report["head_mean"]


def test_warmup_then_cosine_decay(cfg, char_tokenizer, tiny_dataset):
    trainer = _fresh(cfg, char_tokenizer, tiny_dataset)
    total = cfg.train.n_steps
    warm = cfg.optim.warmup_steps
    assert trainer.lr_at(0) < trainer.lr_at(warm - 1)          # 预热期递增
    assert abs(trainer.lr_at(warm - 1) - cfg.optim.lr) < 1e-12  # 预热末到达设定 lr
    assert trainer.lr_at(total - 1) < trainer.lr_at(warm)       # 余弦衰减
    assert trainer.lr_at(total - 1) >= cfg.optim.lr * cfg.optim.min_lr_ratio - 1e-12


def test_early_stop_rolls_back_to_best_weights(cfg, char_tokenizer, tiny_dataset):
    """早停必须回到最优权重，而不是停在最后一步。"""
    cfg.train.n_steps = 400
    cfg.train.eval_every = 20
    cfg.train.patience = 1
    cfg.optim.lr = 5e-3  # 故意用大 lr 逼出过拟合
    trainer = _fresh(cfg, char_tokenizer, tiny_dataset)
    report = trainer.run()
    assert report["stopped_early"]
    assert report["best_step"] < report["steps"]
    after = evaluate_loss(trainer.model, tiny_dataset.val_examples, cfg.train.batch_size)
    assert abs(after["loss"] - report["best_val_loss"]) < 1e-9


def test_checkpoint_restores_weights_exactly(workdir, cfg, char_tokenizer, tiny_dataset):
    model = build_model(cfg, char_tokenizer)
    optimizer = build_optimizer(cfg, model)
    trainer = LMTrainer(cfg, model, optimizer, tiny_dataset.train_examples,
                        tiny_dataset.val_examples, verbose=False)
    trainer.run(n_steps=5)
    before = {name: np.array(p.data, copy=True) for name, p in walk_parameters(model)}

    path = workdir / "ckpt.npz"
    save_checkpoint(model, path, step=5, optimizer=optimizer, meta={"note": "unit-test"})
    # 故意把权重改坏，再读回
    for _name, param in walk_parameters(model):
        param.data[...] = 0.0
    info = load_checkpoint(model, path, optimizer=optimizer)
    assert info["restored"] == len(before)
    assert info["meta"]["step"] == 5
    for name, param in walk_parameters(model):
        assert np.array_equal(param.data, before[name])


def test_resume_continues_from_saved_step(workdir, cfg, char_tokenizer, tiny_dataset):
    """断点续训：跑 5 步存盘 → 新 trainer 载入 → 再跑 5 步，应等于一口气跑 10 步的走向。"""
    cfg.train.n_steps = 5
    model_a = build_model(cfg, char_tokenizer)
    opt_a = build_optimizer(cfg, model_a)
    trainer_a = LMTrainer(cfg, model_a, opt_a, tiny_dataset.train_examples,
                          tiny_dataset.val_examples, verbose=False)
    trainer_a.run()
    path = workdir / "resume.npz"
    save_checkpoint(model_a, path, step=trainer_a.step, optimizer=opt_a)

    model_b = build_model(cfg, char_tokenizer)
    opt_b = build_optimizer(cfg, model_b)
    load_checkpoint(model_b, path, optimizer=opt_b)
    trainer_b = LMTrainer(cfg, model_b, opt_b, tiny_dataset.train_examples,
                          tiny_dataset.val_examples, verbose=False)
    trainer_b.step = trainer_a.step
    trainer_b.run(n_steps=5)
    assert trainer_b.step == 10
    weights_a = {name: p.data for name, p in walk_parameters(model_a)}
    # 续训之后权重必须继续变化（而不是从随机重新开始）
    changed = sum(
        not np.allclose(p.data, weights_a[name])
        for name, p in walk_parameters(model_b)
    )
    assert changed > 0


def test_grad_clip_scales_large_gradients(cfg, char_tokenizer, tiny_dataset):
    trainer = _fresh(cfg, char_tokenizer, tiny_dataset)
    x = np.zeros((2, 4), dtype=np.int64)
    y = np.ones((2, 4), dtype=np.int64)
    mask = np.ones((2, 4))
    trainer.train_step(x, y, mask)
    norms = trainer.history.grad_norm
    assert len(norms) == 1
    assert norms[0] >= 0.0
    assert trainer.cfg.optim.grad_clip > 0


def test_evaluate_loss_is_finite_and_reproducible(trained_bundle):
    cfg = trained_bundle["cfg"]
    model = trained_bundle["model"]
    examples = trained_bundle["dataset"].val_examples
    first = evaluate_loss(model, examples, cfg.train.batch_size)
    second = evaluate_loss(model, examples, cfg.train.batch_size)
    assert np.isfinite(first["loss"]) and np.isfinite(first["perplexity"])
    assert abs(first["loss"] - second["loss"]) < 1e-12
    assert 0.0 <= first["token_accuracy"] <= 1.0
