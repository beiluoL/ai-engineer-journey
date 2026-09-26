"""06 章：把「点积 / 余弦 / 欧氏距离」的数字摆在一起看。

核心结论：向量先归一化后，点积 == 余弦相似度；三种度量的方向要记牢。
"""

from __future__ import annotations

from common import head, note, rule

from rag.similarity import (cosine_similarity, dot, l2_distance, l2_norm, normalize)

A = [3.0, 4.0, 0.0]
B = [0.0, 1.0, 2.0]
UNNORMALIZED = [10.0, -3.0, 2.5]


def main() -> int:
    head("python demos/demo_06_similarity.py")

    rule("① 原始向量")
    print(f"    a    = {A}")
    print(f"    b    = {B}")
    print(f"    |a|  = {l2_norm(A):.6f}    |b| = {l2_norm(B):.6f}")

    rule("② 三种度量（注意方向：距离越小越相似，相似度越大越相似）")
    print(f"    a·b             = {dot(A, B):>12.6f}      点积")
    print(f"    cosine(a, b)    = {cosine_similarity(A, B):>12.6f}      余弦")
    print(f"    l2_distance(a,b)= {l2_distance(A, B):>12.6f}      欧氏距离")
    print(f"    → 余弦 ≤ 1，距离 ≥ 0；两者不是同一个方向的量")

    rule("③ 归一化之后：点积 == 余弦（同一个数字的两种写法）")
    na, nb = normalize(A), normalize(B)
    print(f"    normalize(a) = [{', '.join(f'{x:+.4f}' for x in na)}]   |na| = {l2_norm(na):.6f}")
    print(f"    normalize(b) = [{', '.join(f'{x:+.4f}' for x in nb)}]   |nb| = {l2_norm(nb):.6f}")
    print(f"    dot(na, nb)          = {dot(na, nb):.12f}")
    print(f"    cosine(a, b)         = {cosine_similarity(A, B):.12f}")
    print(f"    两者相等（误差 < 1e-12）："
          f"{abs(dot(na, nb) - cosine_similarity(A, B)) < 1e-12}")

    rule("④ 为什么向量库偏爱余弦 / 内积：和模长无关")
    scaled = [x * 7.0 for x in A]                       # 同一个方向，只是长度不同
    print(f"    a 与 7a 的余弦 = {cosine_similarity(A, scaled):.6f}（仍然是 1）")
    print(f"    a 与 7a 的距离 = {l2_distance(A, scaled):.6f}（距离随模长爆炸）")

    rule("⑤ 零向量没有方向：必须显式报错，不能返回 nan")
    try:
        cosine_similarity([0.0, 0.0, 0.0], A)
    except ValueError as e:
        print(f"    ValueError: {e}")
    note("nan 混进排序会静默打乱 top_k；这里选择直接抛错")

    rule("⑥ 未缩放向量直接的点积 ≠ 余弦（数字看着一样其实差 1000 倍）")
    x, y = UNNORMALIZED, [2.0, 5.0, 1.0]
    print(f"    dot(x, y)       = {dot(x, y):.4f}")
    print(f"    cosine(x, y)    = {cosine_similarity(x, y):.4f}")
    print(f"    dot(norm(x), y) = {dot(normalize(x), y):.4f}（归一化后的点积，才是可比量）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
