"""相似度度量（对应 milestone 06）。

本章的三个主角（06 §3.1 的表）：

    度量        公式                        取值范围     受模长影响
    点积        a·b                        (-∞,+∞)      受
    余弦        a·b/(|a||b|)               [-1,1]       不受
    欧氏距离    √Σ(aᵢ-bᵢ)²                 [0,+∞)       受（越小越相似）

必须记住的两条纪律：
    1. 归一化之后点积 == 余弦（06 §3.2 的三步等价式），所以向量库只需要实现点积；
    2. 分数只用于排序，不用于解读 —— 别写 `if score > 0.75: trust it` 这种魔法阈值。

NumPy 说明：本文件优先用 NumPy 做批量计算（matrix @ query 一行顶双重循环）。
若环境里没有 NumPy，会退回同结果的纯 Python 实现并在 docstring 里注明，
两条路径的结果完全一致（06 章坑 2：比较浮点一律用容差，不用 ==）。
"""

from __future__ import annotations

import math

try:  # NumPy 是可选依赖：装了走矩阵乘法，没装退回纯 Python
    import numpy as np

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover - 无 NumPy 的机器才会走到
    np = None  # type: ignore[assignment]
    _HAS_NUMPY = False


def _as_vector(a) -> list[float]:
    """把 list / np.ndarray 统一成 list[float]。"""
    return [float(x) for x in a]


def l2_norm(a) -> float:
    """向量模长 |a|。"""
    return math.sqrt(sum(x * x for x in _as_vector(a)))


def dot(a, b) -> float:
    """点积 a·b。等长校验放在入口，避免 zip 静默丢维度（06 章坑 1 的防线）。"""
    va, vb = _as_vector(a), _as_vector(b)
    if len(va) != len(vb):
        raise ValueError(f"维度不一致: {len(va)} vs {len(vb)}")
    return sum(x * y for x, y in zip(va, vb))


def cosine_similarity(a, b) -> float:
    """余弦相似度，纯 Python 版（06 §3.3 的手写实现）。

    零向量没有方向，余弦无定义 —— 这里显式抛 ValueError，
    绝不返回 nan（06 章坑 1：nan 会一路污染 argsort 的排序结果）。
    """
    va, vb = _as_vector(a), _as_vector(b)
    if len(va) != len(vb):
        raise ValueError(f"维度不一致: {len(va)} vs {len(vb)}")
    norm_a = math.sqrt(sum(x * x for x in va))
    norm_b = math.sqrt(sum(x * x for x in vb))
    if norm_a == 0.0 or norm_b == 0.0:
        raise ValueError("零向量没有方向，余弦相似度无定义")
    return sum(x * y for x, y in zip(va, vb)) / (norm_a * norm_b)


def l2_distance(a, b) -> float:
    """欧氏距离。注意它**越小越相似**，和相似度方向相反（06 章坑 4）。"""
    va, vb = _as_vector(a), _as_vector(b)
    if len(va) != len(vb):
        raise ValueError(f"维度不一致: {len(va)} vs {len(vb)}")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(va, vb)))


def normalize(vec) -> list[float]:
    """L2 归一化（除以模长）。零向量直接报错而不是返回全 0。"""
    v = _as_vector(vec)
    n = l2_norm(v)
    if n == 0.0:
        raise ValueError("零向量无法归一化")
    return [x / n for x in v]


def cosine_similarity_matrix(matrix, query) -> list[float]:
    """批量余弦：齐次返回「matrix 的每一行」与 query 的相似度，长度 = len(matrix)。

    NumPy 版就是 doc 里的 `matrix @ query`（先按行归一化，再用点积代替余弦）；
    没有 NumPy 时用等价的纯 Python 循环兜底，结果一致。
    """
    rows = [_as_vector(r) for r in matrix]
    q = _as_vector(query)
    if not _HAS_NUMPY:
        return [cosine_similarity(r, q) for r in rows]

    mat = np.asarray(rows, dtype=np.float64)
    qv = np.asarray(q, dtype=np.float64)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    if np.any(norms == 0.0):
        raise ValueError("输入中包含零向量，无法归一化")
    q_norm = np.linalg.norm(qv)
    if q_norm == 0.0:
        raise ValueError("零向量无法归一化")
    unit = mat / norms
    return [float(x) for x in (unit @ (qv / q_norm))]


def dot_product_matrix(matrix, query) -> list[float]:
    """齐次返回「matrix 的每一行」与 query 的点积（**未归一化**的分）。

    用来验证「归一化前后点积 == 余弦」：对已归一化的向量，
    本函数的结果应当与 cosine_similarity_matrix 完全一致（06 §3.2）。
    """
    rows = [_as_vector(r) for r in matrix]
    q = _as_vector(query)
    if not _HAS_NUMPY:
        return [dot(r, q) for r in rows]
    mat = np.asarray(rows, dtype=np.float64)
    qv = np.asarray(q, dtype=np.float64)
    return [float(x) for x in (mat @ qv)]


def cosine_top_k(matrix, query, k: int = 5) -> list[tuple[int, float]]:
    """在齐次矩阵里取与 query 最像的前 k 行，返回 [(原 matrix 下标, 分数), ...] 降序。

    方向纪律（06 章坑 4）：argsort 默认**升序**，相似度要取负号再取头部。
    """
    if not matrix:
        return []
    scores = cosine_similarity_matrix(matrix, query)
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return [(i, scores[i]) for i in order[: min(k, len(order))]]
