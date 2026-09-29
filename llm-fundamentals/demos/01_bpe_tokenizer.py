#!/usr/bin/env python3
"""01 · 极简 BPE 分词器：从字符出发，每轮合并出现次数最高的相邻符号对。

大模型不认识"字符"，只认识整数 id。BPE（Byte-Pair Encoding）是 GPT 系列使用的
分词算法：先把文本拆成最小单位，再反复把"最常挨在一起的两个符号"合并成一个新符号。

运行：
    python3 demos/01_bpe_tokenizer.py
"""
from collections import Counter

CORPUS = [
    "low", "lower", "lowest", "lowering",
    "new", "newer", "newest", "newing",
]
NUM_MERGES = 12


def tokenize(words):
    """初始状态：每个单词拆成字符，末尾加 </w> 表示词边界。"""
    return Counter([" ".join(list(w) + ["</w>"]) for w in words])


def get_pair_stats(vocab):
    """统计所有相邻符号对的出现次数（按单词频次加权）。"""
    pairs = Counter()
    for word, freq in vocab.items():
        symbols = word.split()
        for i in range(len(symbols) - 1):
            pairs[(symbols[i], symbols[i + 1])] += freq
    return pairs


def merge_pair(pair, vocab):
    """把词表中所有出现该 pair 的地方合并成一个新符号。"""
    out = {}
    bigram = " ".join(pair)
    replacement = "".join(pair)
    for word, freq in vocab.items():
        out[word.replace(bigram, replacement)] = freq
    return out


def main():
    vocab = tokenize(CORPUS)
    print("语料:", " ".join(CORPUS))
    print("初始词表(字符级):", sorted({s for w in vocab for s in w.split()}))
    print(f"初始 token 总数: {sum(len(w.split()) * f for w, f in vocab.items())}")
    print()
    print("合并过程 —— 每轮选出现次数最高的相邻对：")
    print(f"{'轮次':<6}{'合并对':<16}{'出现次数':<10}{'合并后 token 总数'}")
    merges = []
    for step in range(NUM_MERGES):
        pairs = get_pair_stats(vocab)
        if not pairs:
            break
        best, cnt = pairs.most_common(1)[0]
        merges.append(best)
        vocab = merge_pair(best, vocab)
        total = sum(len(w.split()) * f for w, f in vocab.items())  # 合并之后的 token 总数
        print(f"{step + 1:<6}{best[0] + '+' + best[1]:<16}{cnt:<10}{total}")

    total_after = sum(len(w.split()) * f for w, f in vocab.items())
    print()
    print(f"合并 {len(merges)} 次后 token 总数: {total_after}  (越合并越少 = 常见词被压成整块)")
    print("学到的合并规则:", " | ".join(a + "+" + b for a, b in merges[:6]), "...")

    # 用学到的规则切一个新词
    word = "lowest"
    symbols = list(word) + ["</w>"]
    for a, b in merges:
        i = 0
        while i < len(symbols) - 1:
            if symbols[i] == a and symbols[i + 1] == b:
                symbols[i : i + 2] = [a + b]
            else:
                i += 1
    print(f'新词 "{word}" 被切成: {symbols}')

    # 中英文的 token 效率对照（启发式：BPE 对中文更"费" token）
    en, zh = "The quick brown fox jumps", "那只敏捷的棕色狐狸跳了过去"
    print()
    print("字符数 vs 近似 token 数（GPT 系规则：英文 ~4 字符/token，中文 ~1.5 字/token）")
    print(f"  英文: {len(en)} 字符 -> ~{round(len(en) / 4)} tokens")
    print(f"  中文: {len(zh)} 字符 -> ~{round(len(zh) / 1.5)} tokens")


if __name__ == "__main__":
    main()
