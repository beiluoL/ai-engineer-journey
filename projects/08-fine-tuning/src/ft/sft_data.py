"""指令微调数据：把 Alpaca 三元组变成「带答案区 mask」的训练样本。

SFT（Supervised Fine-Tuning）和预训练最大的区别在这里：

    预训练：每个 token 都算 loss（模型在学「语言本身」）
    SFT    ：**只有答案区的 token 算 loss**（模型在学「听懂指令并作答」）

为什么必须 mask 掉 prompt：
如果不 mask，一半的梯度会花在让模型「背下用户的问题」上。问题是我们给的，
模型不需要学会生成它；而且让模型去拟合 prompt 的分布，等于把「问答格式」
和「领域知识」两件事混在一起学，既浪费参数又容易让模型学会复读 prompt。
Alpaca/ShareGPT 系数据集的默认做法就是 **completion-only loss**（只算回答）。

本模块把一条记录渲染成：

    ### 指令:
    {instruction}
    ### 输入:
    {input}          ← input 为空则整段省略
    ### 回答:
    {output}<eos>
    └── prompt ──┘└── answer ──┘
       mask = 0      mask = 1

并把 mask 可视化出来 —— 「mask 到底落在哪」这件事光看数字是看不懂的。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from .paths import ensure_p06_importable, ensure_p07_dataset

ensure_p06_importable()

from tokenizer.base import EOS_ID, PAD_ID  # noqa: E402

__all__ = [
    "EOS_ID",
    "PAD_ID",
    "SFTExample",
    "build_lm_examples",
    "build_sft_examples",
    "dataset_stats",
    "load_java_records",
    "pad_batch",
    "render_example",
    "visualize_example",
]

#: Alpaca 指令模板的中文版（保持三段式结构，便于 mask 定位）
PROMPT_TEMPLATE = "### 指令:\n{instruction}\n\n### 回答:\n"
PROMPT_TEMPLATE_WITH_INPUT = "### 指令:\n{instruction}\n\n### 输入:\n{input}\n\n### 回答:\n"


# ==========================================================================
#  数据加载与渲染
# ==========================================================================


def load_java_records() -> list[dict]:
    """只读加载 P07 手写的 Java 面试数据集（Alpaca 结构）。"""
    path = ensure_p07_dataset()
    with open(path, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    if not isinstance(records, list):
        raise TypeError(f"{path} 应该是一个数组，收到 {type(records).__name__}")
    return records


def render_example(record: dict) -> tuple[str, str]:
    """``(instruction, input, output)`` → ``(prompt_text, answer_text)``。"""
    instruction = (record.get("instruction") or "").strip()
    inp = (record.get("input") or "").strip()
    output = (record.get("output") or "").strip()
    if inp:
        prompt = PROMPT_TEMPLATE_WITH_INPUT.format(instruction=instruction, input=inp)
    else:
        prompt = PROMPT_TEMPLATE.format(instruction=instruction)
    return prompt, output


# ==========================================================================
#  构造训练样本
# ==========================================================================


@dataclass
class SFTExample:
    """一条 SFT 样本 + 它的可视化元信息。"""

    x: np.ndarray  # 输入 id（ids[:-1]）
    y: np.ndarray  # 目标 id（ids[1:]）
    mask: np.ndarray  # 1 = 该位置属于答案区，计入 loss
    prompt_text: str
    answer_text: str
    n_prompt: int
    n_answer: int
    truncated: bool

    @property
    def length(self) -> int:
        return int(self.y.shape[0])

    @property
    def mask_coverage(self) -> float:
        return float(self.mask.sum() / self.mask.size)


def build_sft_examples(
    records: list[dict],
    tokenizer,
    max_len: int = 256,
    add_eos: bool = True,
) -> list[SFTExample]:
    """把 Alpaca 记录变成 ``(x, y, mask)`` 样本。

    超长样本**从左侧截断**（丢掉 prompt 的开头），保证答案区永远完整留在窗口里
    —— prompt 少看几个字无所谓，答案被截断才是真的丢监督信号。
    """
    examples: list[SFTExample] = []
    for rec in records:
        prompt_text, answer_text = render_example(rec)
        prompt_ids = list(tokenizer.encode(prompt_text))
        answer_ids = list(tokenizer.encode(answer_text))
        if add_eos:
            answer_ids.append(EOS_ID)
        n_prompt, n_answer = len(prompt_ids), len(answer_ids)

        ids = prompt_ids + answer_ids
        truncated = len(ids) > max_len
        if truncated:
            drop = len(ids) - max_len
            ids = ids[drop:]
            n_prompt = max(0, n_prompt - drop)

        ids_arr = np.asarray(ids, dtype=np.int64)
        x = ids_arr[:-1]
        y = ids_arr[1:]
        # y[i] 对应 ids[i+1]；答案区从 n_prompt 开始 → mask[i]=1 iff i+1 >= n_prompt
        pos = np.arange(1, ids_arr.size, dtype=np.int64)
        mask = (pos >= n_prompt).astype(np.float64)
        examples.append(
            SFTExample(
                x=x, y=y, mask=mask,
                prompt_text=prompt_text, answer_text=answer_text,
                n_prompt=n_prompt, n_answer=n_answer, truncated=truncated,
            )
        )
    return examples


def build_lm_examples(
    text: str,
    tokenizer,
    max_len: int = 256,
    stride: "int | None" = None,
) -> list[SFTExample]:
    """通用语料 → 普通语言模型样本（mask 全 1，即每个 token 都计入 loss）。

    用来算「通用困惑度」，检查微调有没有把通用能力搞坏。
    """
    stride = stride or max_len
    ids_all = list(tokenizer.encode(text))
    examples: list[SFTExample] = []
    for start in range(0, max(1, len(ids_all) - 1), stride):
        chunk = ids_all[start : start + max_len]
        if len(chunk) < 2:
            continue
        arr = np.asarray(chunk, dtype=np.int64)
        examples.append(
            SFTExample(
                x=arr[:-1], y=arr[1:], mask=np.ones(arr.size - 1, dtype=np.float64),
                prompt_text="", answer_text="", n_prompt=0, n_answer=arr.size - 1,
                truncated=False,
            )
        )
    return examples


def pad_batch(examples: list[SFTExample], pad_id: int = PAD_ID):
    """把一批变长样本右侧补齐成 ``(X, Y, M)``。"""
    max_len = max(e.length for e in examples)
    B = len(examples)
    X = np.full((B, max_len), pad_id, dtype=np.int64)
    Y = np.full((B, max_len), pad_id, dtype=np.int64)
    M = np.zeros((B, max_len), dtype=np.float64)
    for i, e in enumerate(examples):
        L = e.length
        X[i, :L] = e.x
        Y[i, :L] = e.y
        M[i, :L] = e.mask
    return X, Y, M


# ==========================================================================
#  统计与可视化
# ==========================================================================


def dataset_stats(records: list[dict], tokenizer, max_len: int = 256) -> dict:
    """数据集的真实统计（全部来自 encode，不猜）。"""
    examples = build_sft_examples(records, tokenizer, max_len=max_len)
    n = len(examples)
    lens = np.array([e.length for e in examples], dtype=np.float64)
    prompt_lens = np.array([e.n_prompt for e in examples], dtype=np.float64)
    answer_lens = np.array([e.n_answer for e in examples], dtype=np.float64)
    total_tokens = float(lens.sum())
    answer_tokens = float(np.array([e.mask.sum() for e in examples]).sum())
    instr_chars = np.array([len((r.get("instruction") or "")) for r in records], dtype=np.float64)
    out_chars = np.array([len((r.get("output") or "")) for r in records], dtype=np.float64)
    return {
        "n_records": n,
        "vocab_size": tokenizer.vocab_size,
        "total_tokens": int(total_tokens),
        "answer_tokens": int(answer_tokens),
        "mask_coverage": answer_tokens / total_tokens if total_tokens else 0.0,
        "len_mean": float(lens.mean()),
        "len_min": int(lens.min()),
        "len_max": int(lens.max()),
        "len_median": float(np.median(lens)),
        "len_p90": float(np.percentile(lens, 90)),
        "prompt_len_mean": float(prompt_lens.mean()),
        "answer_len_mean": float(answer_lens.mean()),
        "instr_chars_mean": float(instr_chars.mean()),
        "output_chars_mean": float(out_chars.mean()),
        "n_truncated": int(sum(1 for e in examples if e.truncated)),
        "n_with_input": int(sum(1 for r in records if (r.get("input") or "").strip())),
    }


def visualize_example(
    example: SFTExample,
    tokenizer,
    max_show: int = 72,
) -> str:
    """把一条样本的 mask 打印成人一眼能看懂的样子。"""
    y = example.y.tolist()
    mask = example.mask
    tokens = [tokenizer.decode([i]) for i in y]
    shown = min(len(tokens), max_show)
    more = " …" if len(tokens) > shown else ""

    def _row(values: list[str]) -> str:
        return "".join(values[:shown]) + more

    mask_row = _row(["·" if m < 0.5 else "1" for m in mask])
    text_row = _row(tokens)
    lines = [
        f"  样本长度 {example.length} 个 token（prompt {example.n_prompt} / answer {example.n_answer}）",
        f"  y     : {text_row}",
        f"  mask  : {mask_row}      （· = 不计入 loss，1 = 计入）",
        f"  答案区占比: {int(mask.sum())}/{example.length} = {example.mask_coverage:.1%}"
        + ("  ⚠ 该样本被左侧截断" if example.truncated else ""),
    ]
    return "\n".join(lines)
