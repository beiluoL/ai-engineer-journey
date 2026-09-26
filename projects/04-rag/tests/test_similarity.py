"""similarity.py：纯数学。这里最容易出的错是「忘了归一化就用点积冒充余弦」。"""

from __future__ import annotations

import math

import pytest

from rag.similarity import (cosine_similarity, cosine_similarity_matrix, cosine_top_k,
                           dot, l2_distance, l2_norm, normalize)


def test_自身余弦为1():
    v = [3.0, 4.0, 0.0]
    assert math.isclose(cosine_similarity(v, v), 1.0, abs_tol=1e-9)


def test_正交向量余弦为0():
    assert math.isclose(cosine_similarity([1, 0], [0, 1]), 0.0, abs_tol=1e-9)


def test_反平行向量余弦为_minus_1():
    assert math.isclose(cosine_similarity([1, 2], [-1, -2]), -1.0, abs_tol=1e-9)


def test_点积与余弦的关系():
    a, b = [1.0, 2.0, 3.0], [4.0, 5.0, 6.0]
    assert math.isclose(dot(a, b), 32.0)
    assert math.isclose(cosine_similarity(a, b), dot(a, b) / (l2_norm(a) * l2_norm(b)))


def test_归一化后点积等于余弦():
    a, b = [1.0, 2.0, 3.0], [0.5, -1.0, 2.0]
    na, nb = normalize(a), normalize(b)
    assert math.isclose(dot(na, nb), cosine_similarity(a, b), abs_tol=1e-9)


def test_normalize_是幂等的且向量模长为1():
    v = [3.0, 4.0]
    n = normalize(v)
    assert math.isclose(l2_norm(n), 1.0, abs_tol=1e-9)
    assert n == normalize(n)


def test_l2_distance_与余弦互补():
    a, b = [1.0, 0.0], [0.0, 1.0]
    assert math.isclose(l2_distance(a, b), math.sqrt(2.0), abs_tol=1e-9)
    assert math.isclose(l2_distance(a, a), 0.0, abs_tol=1e-9)


def test_零向量显式报错_绝不返回nan():                        # nan 会污染排序，06 章坑 1
    with pytest.raises(ValueError):
        cosine_similarity([0, 0], [1, 2])
    with pytest.raises(ValueError):
        normalize([0.0, 0.0])


def test_维度不一致直接报错():
    with pytest.raises(ValueError):
        cosine_similarity([1, 2], [1, 2, 3])
    with pytest.raises(ValueError):
        dot([1, 2], [1])


def test_cosine_top_k_按分排序():
    matrix = [[1.0, 0.0], [1.0, 0.1], [0.0, 1.0]]
    top = cosine_top_k(matrix, [1.0, 0.0], k=2)
    assert [i for i, _ in top] == [0, 1]                   # 与 query 同向的排前面
    scores = [s for _i, s in top]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_cosine_similarity_matrix_一行算完全部():
    matrix = [[1.0, 0.0], [0.0, 1.0]]
    scores = cosine_similarity_matrix(matrix, [1.0, 0.0])
    assert len(scores) == 2
    assert scores[0] > scores[1]
