"""基座模型：用 P06 的 Transformer，在通用语料上预训练一次，然后缓存。

本项目的叙事是「**让通用模型变成领域模型**」，所以必须先有一个「通用但弱」的
基座。它满足三点：

1. **真的用 P06 的架构**（Decoder-Only Transformer + 自写 autograd），
   P08 一行架构代码都不重写。
2. **预训练一次、缓存到 ``models/base_lm.npz``**。
   九个 demo 都要用它，每次重训既浪费时间又会让数字漂移 —— 缓存之后
   所有 demo 看到的都是**同一个基座**，对比才有意义。
3. **确定性**：``np.random.seed(0)`` + 固定 batch 顺序，任何机器上
   训出来的权重都是同一份。

规模选择（以及偏离建议的真实原因）：
建议里写的是 ``seq_len<=64``，但实测 P07 的 Java 数据集**平均一条记录 205 个
字符 / BPE 166 个 token，最长 251**。seq_len=64 会让绝大多数样本的答案被切掉，
「只在答案区算 loss」就变成了一句空话。所以这里取 ``max_len=256``
（实测 4×256 前向+反向约 0.086 s/步）。词表同理：数据集有 **876 个不同字符**，
300~600 的词表必然引入 <unk>，因此取 BPE vocab=1024。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .paths import P08_MODELS, ensure_dir, ensure_p06_importable

ensure_p06_importable()

from model import Adam, TransformerLM, cross_entropy  # noqa: E402
from model.autograd import Parameter  # noqa: E402
from tokenizer import BPETokenizer  # noqa: E402
from tokenizer.sample_corpus import SAMPLE_CORPUS  # noqa: E402

from .inject import named_parameters, set_param  # noqa: E402
from .sft_data import load_java_records, pad_batch, render_example  # noqa: E402

__all__ = [
    "DEFAULT_CONFIG",
    "ModelConfig",
    "build_base_model",
    "build_tokenizer",
    "ensure_base_model",
    "general_corpus",
    "load_base_model",
    "pretrain_model",
    "save_base_model",
]

BASE_NPZ = P08_MODELS / "base_lm.npz"
BASE_META = P08_MODELS / "base_lm_meta.json"
TOKENIZER_JSON = P08_MODELS / "bpe_tokenizer.json"


@dataclass
class ModelConfig:
    """基座模型的规模配置（够小又够真）。"""

    d_model: int = 64
    n_heads: int = 4
    d_ff: int = 256
    n_layers: int = 2
    max_len: int = 256
    vocab_size: int = 1024

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_CONFIG = ModelConfig()


# ==========================================================================
#  语料
# ==========================================================================


def general_corpus() -> tuple[list[str], list[str]]:
    """P06 内置通用语料，切成 ``(预训练行, 评估行)``。

    评估行**不参与预训练**，这样「通用困惑度是否暴涨」才是真的在测泛化，
    而不是在测记忆。
    """
    lines = [ln.strip() for ln in SAMPLE_CORPUS.splitlines() if ln.strip()]
    n_eval = 4
    return lines[:-n_eval], lines[-n_eval:]


def _java_corpus() -> str:
    """Java 领域语料（只用来说分词器，基座预训练**不**碰它）。

    ⚠ 这里必须用 :func:`render_example` **渲染后的**文本，而不是直接拼
    instruction+input+output：指令模板里的 ``###`` 这类字符如果没进过分词器
    语料，编码时会整片变成 ``<unk>``（第一版就这么踩过坑 —— 模型看到的
    prompt 开头是三个 <unk>，等于模板白写了）。
    """
    recs = load_java_records()
    chunks = []
    for r in recs:
        prompt, answer = render_example(r)
        chunks.append(prompt + answer)
    return "\n".join(chunks)


# ==========================================================================
#  分词器
# ==========================================================================


def build_tokenizer(force: bool = False) -> BPETokenizer:
    """在「通用语料 + 领域语料」的并集上训 BPE，并缓存到 models/。

    之所以用并集：基座没见过领域词没关系（那正是要微调的原因），
    但**分词器**必须认识它们，否则领域数据会变成一串 <unk>。
    """
    if TOKENIZER_JSON.is_file() and not force:
        return BPETokenizer.load(TOKENIZER_JSON)
    train_lines, eval_lines = general_corpus()
    corpus = "\n".join(train_lines + eval_lines) + "\n" + _java_corpus()
    tok = BPETokenizer.train(corpus, DEFAULT_CONFIG.vocab_size)
    ensure_dir(P08_MODELS)
    tok.save(TOKENIZER_JSON)
    return tok


# ==========================================================================
#  模型构建 / 存盘
# ==========================================================================


def build_base_model(cfg: ModelConfig, seed: int = 0) -> TransformerLM:
    """构造一个随机初始化的 TransformerLM（seed 固定 → 可复现）。"""
    np.random.seed(seed)
    return TransformerLM(
        vocab_size=cfg.vocab_size,
        d_model=cfg.d_model,
        n_heads=cfg.n_heads,
        d_ff=cfg.d_ff,
        n_layers=cfg.n_layers,
        max_len=cfg.max_len,
    )


def save_base_model(model: TransformerLM, path: "str | Path" = BASE_NPZ) -> dict:
    """把所有参数按 path 存成 npz（含 P06 ``parameters()`` 漏掉的词嵌入）。"""
    path = Path(path)
    ensure_dir(path.parent)
    arrays = {p: param.data.copy() for p, param in named_parameters(model)}
    np.savez(path, **arrays)
    return {"path": str(path), "n_arrays": len(arrays), "bytes": path.stat().st_size}


def load_base_model(
    cfg: "ModelConfig | None" = None,
    path: "str | Path" = BASE_NPZ,
) -> TransformerLM:
    """从 npz 恢复基座权重（要求结构一致）。"""
    cfg = cfg or DEFAULT_CONFIG
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"基座权重不存在：{path}（先跑 ensure_base_model 训练/缓存）")
    model = build_base_model(cfg, seed=0)
    blob = np.load(path)
    for p, param in named_parameters(model):
        if p not in blob.files:
            raise KeyError(f"npz 里缺少参数 {p}")
        if blob[p].shape != param.data.shape:
            raise ValueError(f"{p} 形状对不上：npz {blob[p].shape} vs 模型 {param.data.shape}")
        set_param(model, p, Parameter(blob[p].copy()))
    return model


# ==========================================================================
#  预训练
# ==========================================================================


def pretrain_model(
    model: TransformerLM,
    examples: list,
    n_steps: int = 300,
    lr: float = 3e-3,
    batch_size: int = 4,
    seed: int = 0,
    log_every: int = 0,
) -> list[float]:
    """在通用语料上做**全量**预训练（基座阶段，没有 LoRA）。

    返回 loss 曲线。batch 划分由 ``seed + epoch`` 决定，保证可复现。
    """
    # ⚠ 用 P08 自己的 walk 收集参数：P06 的 model.parameters() 会漏掉 token_emb.weight
    params = [p for _path, p in named_parameters(model)]
    opt = Adam(params, lr=lr)
    n = len(examples)
    n_batches = max(1, int(np.ceil(n / batch_size)))
    losses: list[float] = []
    perm_cache: dict[int, list[np.ndarray]] = {}
    for step in range(n_steps):
        epoch, bi = divmod(step, n_batches)
        if epoch not in perm_cache:
            rng = np.random.default_rng(seed + epoch)
            idx = rng.permutation(n)
            perm_cache[epoch] = [idx[i : i + batch_size] for i in range(0, n, batch_size)]
        sel = perm_cache[epoch][bi]
        X, Y, M = pad_batch([examples[int(i)] for i in sel])
        logits = model(X, mask=None)
        loss = cross_entropy(logits, Y, mask=M)
        loss.backward()
        opt.step()
        losses.append(float(loss.data.item()))
        if log_every and (step + 1) % log_every == 0:
            print(f"    [预训练] step {step + 1:>4}/{n_steps}  loss = {losses[-1]:.4f}")
    return losses


def _build_pretrain_examples(tok: BPETokenizer, max_len: int) -> list:
    """通用语料 → 自回归窗口样本（滑窗步长 1，全部 token 计入 loss）。"""
    from model import build_examples

    train_lines, _eval_lines = general_corpus()
    ids: list[int] = []
    for ln in train_lines:
        ids.extend(tok.encode(ln))
        ids.append(tok.encode("\n")[0])  # 换行当分隔
    pairs = build_examples(ids, context_len=max_len)
    from .sft_data import SFTExample

    return [
        SFTExample(
            x=np.asarray(x, dtype=np.int64), y=np.asarray(y, dtype=np.int64),
            mask=np.ones(len(y), dtype=np.float64), prompt_text="", answer_text="",
            n_prompt=0, n_answer=len(y), truncated=False,
        )
        for x, y in pairs
    ]


# ==========================================================================
#  对外主入口
# ==========================================================================


def ensure_base_model(
    force: bool = False,
    n_steps: int = 120,
    lr: float = 1e-3,
    batch_size: int = 4,
    verbose: bool = False,
) -> tuple[TransformerLM, BPETokenizer, dict]:
    """拿到基座模型：有缓存就加载，没有就确定性训练并缓存。

    .. warning:: 为什么是 120 步 / lr=1e-3，而不是更多步 / 更大学习率

       P06 的 ``Tensor._prev`` 是 Python ``set``，``backward()`` 遍历它做拓扑排序，
       set 的迭代顺序取决于对象地址 —— **每次进程启动都不一样**。这不影响数学
       （任何顺序都是合法拓扑序），但会改变梯度累加的浮点求和顺序，带来 ~1e-16
       的差异。训练动力学是混沌的：实测 300 步 × lr=3e-3 时，这点差异被放大成
       **完全不同的基座权重**（两次重建最大差 0.48！）。

       本项目在 :func:`ft.paths.enable_deterministic_autograd` 里已经把 ``_prev``
       换成按创建顺序排列的 list，根因消除了；但步数/学习率仍然留在 120 / 1e-3：
       这是**刻意**的 —— 基座不该把 24 行预训练语料背下来（loss 停在 4.7 而不是
       0.93），它要像"通用但弱"的基座，M09 的遗忘判定才有意义。

    Returns
    -------
    (model, tokenizer, info)
    """
    tok = build_tokenizer()
    cfg = ModelConfig(vocab_size=tok.vocab_size)
    if BASE_NPZ.is_file() and not force:
        model = load_base_model(cfg, BASE_NPZ)
        meta = json.loads(BASE_META.read_text(encoding="utf-8")) if BASE_META.is_file() else {}
        # 注意顺序：meta 里也有 "source"（记载它是怎么训出来的），会被下面的覆盖，
        # 所以必须放在前面，否则「本次是走缓存」这个事实会被写成 "trained"。
        info = {**meta, "source": "cache", "path": str(BASE_NPZ)}
        return model, tok, info

    if verbose:
        print(f"[基座] 未找到缓存，开始确定性预训练（{n_steps} 步）…")
    model = build_base_model(cfg, seed=0)
    examples = _build_pretrain_examples(tok, cfg.max_len)
    losses = pretrain_model(
        model, examples, n_steps=n_steps, lr=lr, batch_size=batch_size,
        seed=0, log_every=50 if verbose else 0,
    )
    saved = save_base_model(model, BASE_NPZ)
    info = {
        "source": "trained",
        "n_steps": n_steps,
        "lr": lr,
        "batch_size": batch_size,
        "n_examples": len(examples),
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "loss_best": min(losses),
        "path": saved["path"],
        "bytes": saved["bytes"],
        "config": cfg.to_dict(),
        "vocab_size": tok.vocab_size,
    }
    ensure_dir(P08_MODELS)
    BASE_META.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return model, tok, info
