#!/usr/bin/env python3
"""Demo 01 —— 字符级分词器 vs BPE：同一份中英混排语料，两种切法的真实对比。

跑法（必须先建 venv）：

    cd projects/06-mini-transformer-llm
    .venv/bin/python demos/demo_01_tokenizer.py

输出同时打到 stdout 和 ``demos/out/demo_01_tokenizer.txt`` ——
文档里贴的数字全部来自这份文件的真实内容，不手改。
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tokenizer import CharTokenizer, BPETokenizer  # noqa: E402
from tokenizer.sample_corpus import MIXED_TEXT, SAMPLE_CORPUS  # noqa: E402

OUT_PATH = ROOT / "demos" / "out" / "demo_01_tokenizer.txt"

#: 用来做「同一句话两种切法」的中英混排样本（字符全部在语料里）
SAMPLE = "Transformer 是一种神经网络架构，它在 2017 年被提出。"


class _Tee:
    """同时写 stdout 和文件 —— 保证「贴进文档的数字」和「终端看到的」是同一份。"""

    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for s in self._streams:
            s.write(data)
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            s.flush()


def rule(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def show_pieces(pieces: list[str], per_line: int = 12) -> None:
    """把 token 片段分行打印，中文也能对齐看着舒服。"""
    for i in range(0, len(pieces), per_line):
        chunk = pieces[i : i + per_line]
        print("    " + " | ".join(f"{p}" for p in chunk))
    print(f"    → 共 {len(pieces)} 个 token")


def main() -> int:
    print("Project 06 — Mini Transformer LLM")
    print("Demo 01: Tokenizer（字符级 vs BPE）")
    print(f"Python {sys.version.split()[0]}")

    # ---------- 1. 语料 ----------
    rule("1. 语料：手写的中英混排小文本（不联网下载）")
    corpus = SAMPLE_CORPUS
    lines = corpus.splitlines()
    print(f"  行数        : {len(lines)}")
    print(f"  字符数      : {len(corpus)}")
    print(f"  唯一字符数  : {len(set(corpus))}")
    print(f"  英文占比    : {sum(c.isascii() and c.isalpha() for c in corpus) / len(corpus):.1%}")
    print(f"  汉字占比    : {sum(chr(0x4E00) <= c <= chr(0x9FFF) for c in corpus) / len(corpus):.1%}")
    print(f"  首行        : {lines[0]}")

    # ---------- 2. 字符级 ----------
    rule("2. CharTokenizer：词表 = 字符集")
    char_tok = CharTokenizer.build(corpus)
    print(f"  vocab_size          : {char_tok.vocab_size} "
          f"（4 个特殊 token + {char_tok.vocab_size - 4} 个字符）")
    print(f"  前 8 个 id          : {char_tok.id_to_token[:8]}")
    print(f"  语料总 token 数     : {len(char_tok.encode(corpus))}")

    print("\n  中英数字混排样本：")
    print(f"    {SAMPLE}")
    print("  字符级切分：")
    show_pieces(char_tok.pieces(SAMPLE))

    ok = char_tok.decode(char_tok.encode(SAMPLE)) == SAMPLE
    print(f"\n  往返一致性 decode(encode(s)) == s : {ok}")

    ids = char_tok.encode(SAMPLE, add_special_tokens=True)
    print(f"  加特殊 token 后长度: {len(char_tok.encode(SAMPLE))} → {len(ids)} "
          f"（<bos>={ids[0]}, <eos>={ids[-1]}）")
    print(f"  skip_special 解码回原文: "
          f"{char_tok.decode(ids, skip_special=True) == SAMPLE}")

    # ---------- 3. BPE 训练 ----------
    rule("3. BPETokenizer：从零跑合并循环")
    target = 500
    bpe = BPETokenizer.train(corpus, target)
    print(f"  目标 vocab_size     : {target}")
    print(f"  基础词表（特殊+字符）: {bpe.base_vocab_size}")
    print(f"  实际 vocab_size     : {bpe.vocab_size}")
    print(f"  学到的合并次数      : {len(bpe.merges)}")

    print("\n  前 12 条合并规则（按学习顺序，越靠前优先级越高）：")
    for rank, (a, b) in enumerate(bpe.merges[:12]):
        print(f"    #{rank:<3} {a!r} + {b!r} → {a + b!r}")

    zh = [a + b for a, b in bpe.merges
          if any(chr(0x4E00) <= ch <= chr(0x9FFF) for ch in a + b)]
    print(f"\n  中文合并（共 {len(zh)} 条），前 16 条：")
    print("    " + " ".join(zh[:16]))

    # ---------- 4. 两种切法的正面对比 ----------
    rule("4. 同一句话：字符级 vs BPE")
    print(f"  样本：{SAMPLE}")
    print("\n  [字符级]")
    show_pieces(char_tok.pieces(SAMPLE))
    print("\n  [BPE]")
    show_pieces(bpe.pieces(SAMPLE))

    char_n = len(char_tok.encode(corpus))
    bpe_n = len(bpe.encode(corpus))
    print(f"\n  整份语料：字符级 {char_n} token → BPE {bpe_n} token，"
          f"压缩率 {char_n / bpe_n:.2f}x")
    print(f"  往返一致性 decode(encode(s)) == s : "
          f"{bpe.decode(bpe.encode(SAMPLE)) == SAMPLE}")
    print(f"  逐行往返一致性（{len(lines)} 行全部自检）："
          f"{all(bpe.decode(bpe.encode(line)) == line for line in lines)}")

    # ---------- 5. 词表增长曲线 ----------
    rule("5. 词表越大，序列越短（真实测量）")
    print(f"  {'目标vocab':>10} {'实际vocab':>10} {'合并数':>8} "
          f"{'语料token':>10} {'样本token':>10} {'压缩率':>8}")
    curve: list[tuple[int, int, int, int, int]] = []
    for cap in (char_tok.vocab_size, 350, 400, 450, 500, 600):
        tok = BPETokenizer.train(corpus, cap)
        n_corpus = len(tok.encode(corpus))
        n_sample = len(tok.encode(SAMPLE))
        curve.append((cap, tok.vocab_size, len(tok.merges), n_corpus, n_sample))
        print(f"  {cap:>10} {tok.vocab_size:>10} {len(tok.merges):>8} "
              f"{n_corpus:>10} {n_sample:>10} {char_n / n_corpus:>7.2f}x")

    # ---------- 6. 特殊 token 与 OOV ----------
    rule("6. 特殊 token 与词表外字符")
    print(f"  <pad>/<unk>/<bos>/<eos> 的 id："
          f"{[char_tok.vocab[t] for t in ('<pad>', '<unk>', '<bos>', '<eos>')]}")
    print(f"  词表外的句子：{MIXED_TEXT}")
    oov_ids = bpe.encode(MIXED_TEXT)
    print(f"  BPE 编码后 token 数：{len(oov_ids)}，其中 <unk>(id=1) 出现 "
          f"{oov_ids.count(1)} 次")
    print(f"    片段：{bpe.pieces(MIXED_TEXT)}")
    print("  → 词表里没有的字符只能塌成 <unk>，原文信息在这里就丢了；")
    print("    这正是「训练和推理必须用同一份词表」的原因。")

    # ---------- 7. 优雅停止 ----------
    rule("7. vocab_size 上限与优雅停止")
    huge = BPETokenizer.train(corpus, 5000)
    print(f"  请求 vocab_size=5000，可合并的 pair 只够用 {len(huge.merges)} 次")
    print(f"  实际 vocab_size={huge.vocab_size}（小于 5000，不抛异常，安静停下）")
    try:
        BPETokenizer.train(corpus, 10)
    except ValueError as exc:
        print(f"  反过来请求 10：直接报错 —— {exc}")

    # ---------- 8. 落盘 / 读回 ----------
    rule("8. 落盘与读回")
    vocab_dir = ROOT / "demos" / "out"
    char_path = char_tok.save(vocab_dir / "char_vocab.json")
    bpe_path = bpe.save(vocab_dir / "bpe_vocab.json")
    print(f"  字符级词表 → {char_path.relative_to(ROOT)}"
          f"（{char_path.stat().st_size} 字节）")
    print(f"  BPE 词表   → {bpe_path.relative_to(ROOT)}"
          f"（{bpe_path.stat().st_size} 字节，含 {len(bpe.merges)} 条有序 merges）")

    reloaded = BPETokenizer.load(bpe_path)
    print(f"  读回后 vocab_size: {reloaded.vocab_size}（与原对象一致："
          f"{reloaded.vocab_size == bpe.vocab_size}）")
    print(f"  读回后 merges 顺序一致: {reloaded.merges == bpe.merges}")
    print(f"  读回后编码结果一致    : "
          f"{reloaded.encode(SAMPLE) == bpe.encode(SAMPLE)}")
    print(f"  读回后往返一致        : "
          f"{reloaded.decode(reloaded.encode(SAMPLE)) == SAMPLE}")

    rule("Demo 01 结束")
    print("  下一步：Milestone 03 —— 用这里的 id 序列去查 Embedding 矩阵。")
    return 0


if __name__ == "__main__":
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh, contextlib.redirect_stdout(
        _Tee(sys.stdout, fh)
    ):
        code = main()
    sys.exit(code)
