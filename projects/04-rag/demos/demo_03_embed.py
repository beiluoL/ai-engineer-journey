"""03 章：FakeEmbeddingClient 真的向量化 —— 维度、前 8 个浮点数、两两余弦。"""

from __future__ import annotations

from common import head, note, rule

from rag.embedding import FakeEmbeddingClient, run_sync
from rag.similarity import cosine_similarity, l2_norm

TEXTS = [
    "生成器为什么能省内存",
    "生成器表达式比列表推导式更省内存",
    "GIL 是 CPython 的一把全局解释器锁",
]


def main() -> int:
    head("python demos/demo_03_embed.py")
    client = FakeEmbeddingClient()
    note(f"离线替身 model_name={client.model_name}，dim={client.dim}")

    print("texts = ")
    for t in TEXTS:
        print(f"    {t!r}")
    vecs = run_sync(client.embed(TEXTS))
    print(f"embed(texts) 返回 {len(vecs)} 个向量，每个 {len(vecs[0])} 维")

    rule("每个向量的前 8 个浮点数 + 模长（都是 L2 归一化过的）")
    for t, v in zip(TEXTS, vecs):
        head8 = ", ".join(f"{x:+.4f}" for x in v[:8])
        print(f"  [{t[:16]:<16}] 前8维 = [{head8} …]  |v| = {l2_norm(v):.6f}")

    rule("两两余弦（共享字面越多的两段，夹角越小）")
    print(f"  {'':<22}{'cos(q0,q1)':>14}{'cos(q0,q2)':>14}{'cos(q1,q2)':>14}")
    for i in range(len(vecs)):
        row = "".join(f"{cosine_similarity(vecs[i], vecs[j]):>14.6f}"
                      for j in range(len(vecs)))
        print(f"  {f'q{i}':<22}{row}")

    q0, q1, q2 = vecs
    print()
    note("q0/q1 都在讲「生成器 + 内存」，余弦明显更高；q2 讲的是 GIL，立刻拉开差距")
    print(f"  cos(q0,q1) = {cosine_similarity(q0, q1):.4f}   "
          f"cos(q0,q2) = {cosine_similarity(q0, q2):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
