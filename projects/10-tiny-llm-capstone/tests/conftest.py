"""Project 10 —— 测试夹具。

和 P06/P08 一致：**不用 pytest 内置的 ``tmp_path``**。本仓库的开发沙箱里
``/private/var/.../pytest-of-unknown`` 不可写，``tmp_path`` 会直接 PermissionError。
所以统一用仓库内的 ``tests/.tmp/``，每个用例独立子目录，跑完自动清理。

另外一个刻意的设计：训练相关的测试用**极小配置**（d_model=32 / 1 层 / 40 步）
而不是默认配置 —— 单元测试要的是「快且稳定」，真实数字由 ``demos/`` 负责产出。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from tiny.config import TinyConfig
from tiny.data import build_dataset, clean_lines, load_corpus, split_lines
from tiny.model import build_model, build_optimizer
from tiny.tok import build_tokenizer
from tiny.train import LMTrainer

REPO_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = REPO_ROOT / "tests" / ".tmp"


@pytest.fixture()
def workdir() -> Path:
    """仓库内的临时目录，用例结束即删。"""
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="case-", dir=TMP_ROOT))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(autouse=True)
def _cleanup_tmp_root():
    yield
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def _guard_real_models_dir():
    """整轮测试期间，真实的 ``models/`` 必须**一个字节都没变**。

    这条守卫是为了一个真实踩过的坑：``tmp_models_dir`` 漏重定向了一个常量，
    测试就把 char 分词器写进了 ``models/tokenizer.json``，而 demo 的缓存
    （BPE 1280 词表 + 对应权重）就住在同一个目录里。结果是**测试全绿、
    demo 全炸**，而且报错是 ``cannot reshape array of size 81920 into shape
    (858, 64)`` 这种完全指不到根因的信息。

    只比较 ``(文件名, 大小, mtime_ns)`` —— 够抓住任何写入，又不依赖内容哈希。
    """
    import tiny.paths as paths_mod

    root = paths_mod.P10_MODELS

    def snapshot() -> dict:
        if not root.is_dir():
            return {}
        return {
            item.name: (item.stat().st_size, item.stat().st_mtime_ns)
            for item in sorted(root.iterdir())
            if item.is_file()
        }

    before = snapshot()
    yield
    after = snapshot()
    if before != after:
        touched = sorted(set(before) | set(after))
        raise AssertionError(
            "测试污染了真实的 models/ 目录（demo 缓存就在那里）：\n  "
            + "\n  ".join(f"{name}: {before.get(name)} -> {after.get(name)}" for name in touched)
            + "\n请检查 tests/conftest.py 的 tmp_models_dir 是否漏重定向了某个路径常量。"
        )


def small_config(**overrides) -> TinyConfig:
    """极小的、秒级可跑完的配置（默认 40 步）。"""
    cfg = TinyConfig()
    cfg.tokenizer.kind = "char"
    cfg.model.d_model = 32
    cfg.model.n_heads = 4
    cfg.model.d_ff = 64
    cfg.model.n_layers = 1
    cfg.model.max_len = 32
    cfg.data.val_ratio = 0.2
    cfg.data.stride = 16
    cfg.optim.lr = 3e-3
    cfg.optim.warmup_steps = 5
    cfg.train.batch_size = 4
    cfg.train.n_steps = 40
    cfg.train.eval_every = 10
    cfg.train.patience = 0
    cfg.train.log_every = 0
    cfg.gen.max_new_tokens = 12
    for key, value in overrides.items():
        section, field_name = key.split("__", 1)
        setattr(getattr(cfg, section), field_name, value)
    return cfg.validate()


@pytest.fixture()
def cfg() -> TinyConfig:
    """每个用例一份**新**配置 —— 用例里改超参不会污染别人。"""
    return small_config()


@pytest.fixture(scope="session")
def session_cfg() -> TinyConfig:
    """会话级配置：给下面几个「训一次全场复用」的昂贵夹具用。"""
    return small_config()


@pytest.fixture(scope="session")
def corpus_lines() -> list[str]:
    return load_corpus(TinyConfig())


@pytest.fixture(scope="session")
def char_tokenizer(session_cfg, corpus_lines):
    kept, _ = clean_lines(corpus_lines, session_cfg.data.min_chars, session_cfg.data.dedup)
    train_lines, _val = split_lines(kept, session_cfg.data.val_ratio, session_cfg.data.seed)
    return build_tokenizer(session_cfg, train_lines)


@pytest.fixture(scope="session")
def tiny_dataset(session_cfg, char_tokenizer, corpus_lines):
    return build_dataset(session_cfg, char_tokenizer, corpus_lines)


@pytest.fixture()
def tmp_models_dir(workdir, monkeypatch):
    """把 ``models/`` 重定向到仓库内的临时目录。

    pipeline 的缓存路径是**模块级常量**，直接跑会把真实 ``models/`` 覆盖掉
    （也让测试之间互相污染）。所以这里整体换掉再还原。

    ⚠ 踩过的坑：``TOKENIZER_JSON`` 这个名字**同时存在于 ``tiny.tok`` 和
    ``tiny.pipeline``**（``pipeline`` 里 ``from .tok import ...`` 时又自己定义了
    一份）。只重定向其中一个，``run_pipeline(force=True)`` 依然会把测试用的
    char 分词器写进真实 ``models/tokenizer.json``，把 demo 的缓存彻底毒掉
    （表现为下一次 demo 报 ``cannot reshape array of size 81920 into shape
    (858,64)``）。所以下面按 ``(模块, 常量名)`` 逐条登记，不按名字去猜模块。
    """
    import tiny.pipeline as pipeline_mod
    import tiny.tok as tok_mod

    target = workdir / "models"
    target.mkdir(parents=True, exist_ok=True)
    targets = [
        (tok_mod, "TOKENIZER_JSON"),
        (pipeline_mod, "TOKENIZER_JSON"),
        (pipeline_mod, "CONFIG_JSON"),
        (pipeline_mod, "MODEL_NPZ"),
        (pipeline_mod, "BEST_NPZ"),
        (pipeline_mod, "REPORT_JSON"),
    ]
    for module, name in targets:
        monkeypatch.setattr(module, name, target / Path(getattr(module, name)).name)
    return target


@pytest.fixture(scope="session")
def trained_bundle(session_cfg, char_tokenizer, tiny_dataset):
    """训好一次、全场复用（避免每个用例都重训）。

    注意：bundle 里的 ``cfg`` 是**会话级**的，用例不要改它 ——
    需要改超参就用函数级的 ``cfg`` 夹具另起炉灶。
    """
    import copy

    cfg = copy.deepcopy(session_cfg)
    model = build_model(cfg, char_tokenizer)
    optimizer = build_optimizer(cfg, model)
    trainer = LMTrainer(cfg, model, optimizer, tiny_dataset.train_examples,
                        tiny_dataset.val_examples, verbose=False)
    report = trainer.run()
    return {
        "cfg": cfg,
        "tokenizer": char_tokenizer,
        "dataset": tiny_dataset,
        "model": model,
        "optimizer": optimizer,
        "report": report,
    }
