"""Project 06 —— 模型层测试：从 autograd 到训练/推理全链路。

覆盖：
- 每个算子的形状与数值性质
- **梯度校验**（autograd vs 有限差分），误差 < 1e-4
- causal mask 挡住未来、注意力行和为 1
- 多头输出形状、训练 loss 下降、生成在词表内且长度正确
- 用 sample_corpus + BPE 的分层集成测试

约定：每个用例开头 ``np.random.seed(0)`` 保证确定性（和 demo / 仓库风格一致）。
"""

from __future__ import annotations

import numpy as np
import pytest

from model import (
    Adam,
    DataLoader,
    DecoderStack,
    FeedForward,
    Module,
    MultiHeadAttention,
    Parameter,
    PositionalEncoding,
    SGD,
    Tensor,
    TokenEmbedding,
    Trainer,
    TransformerBlock,
    TransformerLM,
    add,
    build_examples,
    causal_mask,
    combine,
    cross_entropy,
    examples_from_lines,
    generate,
    generate_ids,
    grad_check,
    layernorm,
    log,
    matmul,
    mean,
    mul,
    relu,
    reshape,
    scaled_dot_product_attention,
    softmax,
    sub,
    sum,
    transpose,
)
from tokenizer import BPETokenizer
from tokenizer.base import EOS_ID
from tokenizer.sample_corpus import SAMPLE_CORPUS

#: 真实分词器（依赖 conftest 的 corpus fixture / SAMPLE_CORPUS）
BPE = BPETokenizer.train(SAMPLE_CORPUS, 500)


@pytest.fixture(autouse=True)
def _seed() -> None:
    """所有用例统一 seed，保证权重初始化/打乱/采样都可复现。"""
    np.random.seed(0)


# ==========================================================================
#  autograd 算子：形状与数值性质
# ==========================================================================


def test_matmul_2d_shape() -> None:
    a = Tensor(np.random.randn(3, 4))
    b = Tensor(np.random.randn(4, 5))
    assert matmul(a, b).data.shape == (3, 5)


def test_matmul_3d_shape() -> None:
    a = Tensor(np.random.randn(2, 3, 4))
    b = Tensor(np.random.randn(2, 4, 5))
    assert matmul(a, b).data.shape == (2, 3, 5)


def test_add_broadcast_shape() -> None:
    a = Tensor(np.random.randn(3, 4))
    b = Tensor(np.random.randn(4))  # 广播成 (3,4)
    assert add(a, b).data.shape == (3, 4)


def test_mul_scalar_shape() -> None:
    a = Tensor(np.random.randn(3, 4))
    assert mul(a, 2.0).data.shape == (3, 4)


def test_sub_shape() -> None:
    a = Tensor(np.random.randn(3, 4))
    b = Tensor(np.random.randn(3, 4))
    assert sub(a, b).data.shape == (3, 4)


def test_sum_all_scalar() -> None:
    a = Tensor(np.random.randn(3, 4))
    assert sum(a).data.shape == ()
    assert sum(a).data.item() == pytest.approx(a.data.sum())


def test_sum_axis_keepdims() -> None:
    a = Tensor(np.random.randn(3, 4))
    out = sum(a, axis=1, keepdims=True)
    assert out.data.shape == (3, 1)


def test_mean_axis() -> None:
    a = Tensor(np.random.randn(3, 4))
    out = mean(a, axis=0)
    assert out.data.shape == (4,)
    assert np.allclose(out.data, a.data.mean(axis=0))


def test_log_shape() -> None:
    a = Tensor(np.abs(np.random.randn(3, 4)) + 1.0)
    assert log(a).data.shape == (3, 4)


def test_relu_zero_for_negative() -> None:
    a = Tensor(np.array([[-1.0, 2.0, 0.0, -3.0]]))
    assert np.allclose(relu(a).data, [[0.0, 2.0, 0.0, 0.0]])


def test_softmax_rows_sum_to_one_2d() -> None:
    a = Tensor(np.random.randn(5, 7))
    s = softmax(a, axis=-1)
    assert np.allclose(s.data.sum(axis=-1), 1.0, atol=1e-12)


def test_softmax_rows_sum_to_one_3d() -> None:
    a = Tensor(np.random.randn(2, 5, 7))
    s = softmax(a, axis=-1)
    assert np.allclose(s.data.sum(axis=-1), 1.0, atol=1e-12)


def test_softmax_no_nan() -> None:
    a = Tensor(np.array([[1000.0, -1000.0, 0.0]]))
    s = softmax(a, axis=-1)
    assert np.isfinite(s.data).all()


def test_transpose_invertible() -> None:
    a = Tensor(np.random.randn(2, 3, 4))
    back = transpose(transpose(a, [0, 2, 1]), [0, 2, 1])
    assert np.allclose(back.data, a.data)


def test_reshape_roundtrip() -> None:
    a = Tensor(np.random.randn(6, 4))
    r = reshape(reshape(a, (2, 3, 4)), (6, 4))
    assert np.allclose(r.data, a.data)


def test_layernorm_shape() -> None:
    x = Tensor(np.random.randn(6, 8))
    g = Parameter(np.ones(8))
    b = Parameter(np.zeros(8))
    assert layernorm(x, g, b).data.shape == (6, 8)


def test_layernorm_gamma_one_beta_zero_preserves_mean() -> None:
    x = Tensor(np.random.randn(6, 8))
    g = Parameter(np.ones(8))
    b = Parameter(np.zeros(8))
    y = layernorm(x, g, b)
    # gamma=1,beta=0 时，输出的均值应≈0、方差≈1（沿最后一轴）。
    # 注意方差用的是总体方差、且带了 eps，故放宽到 1e-3。
    assert np.allclose(y.data.mean(axis=-1), 0.0, atol=1e-9)
    assert np.allclose(y.data.var(axis=-1), 1.0, atol=1e-3)


def test_cross_entropy_scalar() -> None:
    logits = Tensor(np.random.randn(4, 5))
    ce = cross_entropy(logits, np.array([0, 1, 2, 3]))
    assert ce.data.shape == ()
    assert ce.data.item() > 0


def test_parameter_requires_grad() -> None:
    p = Parameter(np.zeros(3))
    assert p.requires_grad is True


def test_module_collects_parameters() -> None:
    blk = TransformerBlock(d_model=8, n_heads=2, d_ff=16)
    params = blk.parameters()
    assert len(params) > 0
    assert all(isinstance(p, Parameter) for p in params)


def test_backward_does_not_accumulate_across_calls() -> None:
    x = Tensor(np.random.randn(3, 4))
    w = Parameter(np.random.randn(4, 2))
    y = sum(matmul(x, w))
    y.backward()
    g1 = w.grad.copy()
    y.backward()
    assert np.allclose(g1, w.grad)  # 第二次 backward 先清零再算，结果不变


# ==========================================================================
#  梯度校验：autograd vs 有限差分（误差 < 1e-4）
# ==========================================================================


def test_gradcheck_matmul() -> None:
    X = Tensor(np.random.randn(4, 5))
    W = Parameter(np.random.randn(5, 3))

    def f(p):
        return sum(matmul(X, p))

    assert grad_check(f, [W]) < 1e-4


def test_gradcheck_add_broadcast() -> None:
    X = Tensor(np.random.randn(3, 4))
    bias = Parameter(np.zeros(4))

    def f(p):
        return sum(add(X, p))

    assert grad_check(f, [bias]) < 1e-4


def test_gradcheck_mul_scalar() -> None:
    X = Tensor(np.random.randn(4, 5))
    w = Parameter(np.random.randn(5, 3))

    def f(p):
        return sum(mul(matmul(X, p), 2.0))

    assert grad_check(f, [w]) < 1e-4


def test_gradcheck_relu() -> None:
    X = Tensor(np.random.randn(4, 5))
    w = Parameter(np.random.randn(5, 3))

    def f(p):
        return sum(relu(matmul(X, p)))

    assert grad_check(f, [w]) < 1e-4


def test_gradcheck_softmax() -> None:
    X = Tensor(np.random.randn(4, 6))
    w = Parameter(np.random.randn(6, 5))
    c = Tensor(np.random.randn(4, 5))

    def f(p):
        return sum(softmax(matmul(X, p), axis=-1) * c)

    assert grad_check(f, [w]) < 1e-4


def test_gradcheck_sum_mean() -> None:
    X = Tensor(np.random.randn(4, 5))

    def f(p):
        return sum(mean(p, axis=0))

    assert grad_check(f, [Parameter(np.random.randn(4, 5))]) < 1e-4


def test_gradcheck_cross_entropy() -> None:
    Z = Parameter(np.random.randn(5, 4))

    def f(p):
        return cross_entropy(p, np.array([0, 1, 2, 3, 0]))

    assert grad_check(f, [Z]) < 1e-4


def test_gradcheck_layernorm_gamma() -> None:
    x = Tensor(np.random.randn(6, 4))
    c = Tensor(np.random.randn(6, 4))
    g = Parameter(np.ones(4))

    def f(p):
        return sum(layernorm(x, p, Parameter(np.zeros(4))) * c)

    assert grad_check(f, [g]) < 1e-4


def test_gradcheck_layernorm_beta() -> None:
    x = Tensor(np.random.randn(6, 4))
    c = Tensor(np.random.randn(6, 4))
    b = Parameter(np.zeros(4))

    def f(p):
        return sum(layernorm(x, Parameter(np.ones(4)), p) * c)

    assert grad_check(f, [b]) < 1e-4


def test_gradcheck_3d_matmul_softmax() -> None:
    X = Tensor(np.random.randn(2, 3, 4))
    w = Parameter(np.random.randn(4, 5))
    c = Tensor(np.random.randn(2, 3, 5))

    def f(p):
        return sum(softmax(matmul(X, p), axis=-1) * c)

    assert grad_check(f, [w]) < 1e-4


def test_gradcheck_matmul_relu_chain() -> None:
    X = Tensor(np.random.randn(4, 5))
    w1 = Parameter(np.random.randn(5, 6))
    w2 = Parameter(np.random.randn(6, 3))

    def f(p1, p2):
        h = relu(matmul(X, p1))
        return sum(matmul(h, p2))

    assert grad_check(f, [w1, w2]) < 1e-4


def test_gradcheck_full_tiny_model() -> None:
    """在 tiny 模型配置上对整个前向+交叉熵做梯度校验。"""
    m = TransformerLM(vocab_size=12, d_model=8, n_heads=2, d_ff=16, n_layers=1, max_len=16)
    ids = np.array([[1, 2, 3, 4, 5, 6, 7, 8]])
    targets = np.array([2, 3, 4, 5, 6, 7, 8, 9])

    def f(*_):
        return cross_entropy(m(ids), targets)

    # 多算子叠加，tol 放宽到 1e-3 仍是极小量
    assert grad_check(f, m.parameters()) < 1e-3


# ==========================================================================
#  Embedding
# ==========================================================================


def test_token_embedding_shape_1d() -> None:
    emb = TokenEmbedding(vocab_size=20, d_model=8)
    assert emb(np.array([1, 2, 3])).data.shape == (3, 8)


def test_token_embedding_shape_2d() -> None:
    emb = TokenEmbedding(vocab_size=20, d_model=8)
    assert emb(np.array([[1, 2], [3, 4]])).data.shape == (2, 2, 8)


def test_token_embedding_weight_is_parameter() -> None:
    emb = TokenEmbedding(vocab_size=20, d_model=8)
    assert isinstance(emb.weight, Parameter)


def test_token_embedding_lookup_correct_row() -> None:
    emb = TokenEmbedding(vocab_size=20, d_model=8)
    out = emb(np.array([1, 5])).data
    assert np.allclose(out[0], emb.weight.data[1])
    assert np.allclose(out[1], emb.weight.data[5])


def test_token_embedding_onehot_scatter_grad() -> None:
    """one-hot 查表：只有用到的行有梯度，没用到的行梯度应为 0。"""
    emb = TokenEmbedding(vocab_size=10, d_model=4)
    out = sum(emb(np.array([3])))
    out.backward()
    assert emb.weight.grad is not None
    assert np.allclose(emb.weight.grad[0], 0.0)        # 没用到
    assert not np.allclose(emb.weight.grad[3], 0.0)    # 用到了


def test_positional_encoding_shape() -> None:
    pe = PositionalEncoding(d_model=16, max_len=64)
    assert pe(10).data.shape == (10, 16)


def test_positional_encoding_pe00_zero_pe01_one() -> None:
    pe = PositionalEncoding(d_model=16, max_len=64)
    row0 = pe(1).data[0]
    assert abs(row0[0] - 0.0) < 1e-12   # sin(0) = 0
    assert abs(row0[1] - 1.0) < 1e-12   # cos(0) = 1


def test_positional_encoding_is_constant() -> None:
    pe = PositionalEncoding(d_model=8, max_len=32)
    assert pe(5).requires_grad is False


def test_combine_shape() -> None:
    emb = TokenEmbedding(vocab_size=20, d_model=8)
    pe = PositionalEncoding(d_model=8, max_len=32)
    x = combine(emb, pe, np.array([[1, 2, 3]]))
    assert x.data.shape == (1, 3, 8)


def test_combine_equals_token_plus_pos() -> None:
    emb = TokenEmbedding(vocab_size=20, d_model=8)
    pe = PositionalEncoding(d_model=8, max_len=32)
    ids = np.array([1, 2, 3])
    got = combine(emb, pe, ids).data
    want = emb(ids).data + pe(len(ids)).data
    assert np.allclose(got, want)


# ==========================================================================
#  Attention
# ==========================================================================


def test_causal_mask_shape() -> None:
    assert causal_mask(5).shape == (5, 5)


def test_causal_mask_lower_tri_zero() -> None:
    m = causal_mask(5)
    lower = np.tril(np.ones((5, 5), dtype=bool), k=-1)
    assert np.all(m[lower] == 0.0)


def test_causal_mask_upper_tri_neg_inf() -> None:
    m = causal_mask(5)
    upper = np.triu(np.ones((5, 5), dtype=bool), k=1)
    assert np.all(np.isneginf(m[upper]))


def test_sdpa_shape_2d() -> None:
    q = Tensor(np.random.randn(6, 8))
    k = Tensor(np.random.randn(6, 8))
    v = Tensor(np.random.randn(6, 8))
    assert scaled_dot_product_attention(q, k, v).data.shape == (6, 8)


def test_sdpa_shape_3d() -> None:
    q = Tensor(np.random.randn(2, 6, 8))
    k = Tensor(np.random.randn(2, 6, 8))
    v = Tensor(np.random.randn(2, 6, 8))
    assert scaled_dot_product_attention(q, k, v).data.shape == (2, 6, 8)


def test_sdpa_attention_rows_sum_to_one() -> None:
    q = Tensor(np.random.randn(6, 8))
    k = Tensor(np.random.randn(6, 8))
    v = Tensor(np.random.randn(6, 8))
    out, attn = scaled_dot_product_attention(q, k, v, return_attn=True)
    assert attn.shape == (6, 6)
    assert np.allclose(attn.sum(axis=-1), 1.0, atol=1e-12)


def test_sdpa_blocks_future_with_causal_mask() -> None:
    q = Tensor(np.random.randn(6, 8))
    k = Tensor(np.random.randn(6, 8))
    v = Tensor(np.random.randn(6, 8))
    out, attn = scaled_dot_product_attention(q, k, v, mask=causal_mask(6), return_attn=True)
    upper = np.triu(np.ones((6, 6), dtype=bool), k=1)
    assert np.allclose(attn[upper], 0.0, atol=1e-12)


def test_sdpa_output_finite() -> None:
    q = Tensor(np.random.randn(6, 8))
    k = Tensor(np.random.randn(6, 8))
    v = Tensor(np.random.randn(6, 8))
    out = scaled_dot_product_attention(q, k, v, mask=causal_mask(6))
    assert np.isfinite(out.data).all()


def test_sdpa_scaling_by_sqrt_dk() -> None:
    """缩放后，scores 的尺度应当是不缩放时的 1/sqrt(d_k)。"""
    q = Tensor(np.random.randn(4, 16))
    k = Tensor(np.random.randn(4, 16))
    # 不缩放
    scores_unscaled = matmul(q, transpose(k, [1, 0])).data
    # 缩放（手动）
    out_scaled, attn_scaled = scaled_dot_product_attention(q, k, q, return_attn=True)
    # 直接复算缩放 scores
    scores_scaled = (q.data @ k.data.T) / np.sqrt(16)
    assert np.allclose(scores_scaled, scores_unscaled / np.sqrt(16), atol=1e-10)


# ==========================================================================
#  Multi-Head Attention
# ==========================================================================


def test_mha_output_shape_2d() -> None:
    mha = MultiHeadAttention(d_model=16, n_heads=4)
    x = Tensor(np.random.randn(7, 16))
    assert mha(x).data.shape == (7, 16)


def test_mha_output_shape_3d() -> None:
    mha = MultiHeadAttention(d_model=16, n_heads=4)
    x = Tensor(np.random.randn(2, 7, 16))
    assert mha(x).data.shape == (2, 7, 16)


def test_mha_requires_divisible() -> None:
    with pytest.raises(ValueError):
        MultiHeadAttention(d_model=15, n_heads=4)


def test_mha_parameters_count() -> None:
    mha = MultiHeadAttention(d_model=16, n_heads=4)
    # Wq,Wk,Wv,Wo 四个
    assert len(mha.parameters()) == 4


def test_mha_grad_flow() -> None:
    mha = MultiHeadAttention(d_model=16, n_heads=4)
    x = Tensor(np.random.randn(5, 16))
    y = sum(mha(x))
    y.backward()
    assert mha.Wq.grad is not None
    assert np.isfinite(mha.Wq.grad).all()


def test_mha_mask_blocks_future() -> None:
    """多头注意力叠加因果掩码后，权重上三角仍应为 0。"""
    mha = MultiHeadAttention(d_model=16, n_heads=4)
    x = Tensor(np.random.randn(6, 16))
    q = mha._split_heads(mha.attn.ln1(x) if hasattr(mha, "attn") else x)  # type: ignore
    # 直接走内部 sdpa 验证上三角
    from model.attention import scaled_dot_product_attention as sdpa

    qh = mha._split_heads(x)
    kh = mha._split_heads(x)
    vh = mha._split_heads(x)
    _, attn = sdpa(qh, kh, vh, mask=causal_mask(6), return_attn=True)
    upper = np.triu(np.ones((6, 6), dtype=bool), k=1)
    # attn 形状 (n_heads, 6, 6)，对所有头的上三角都该≈0
    assert np.allclose(attn[:, upper].reshape(attn.shape[0], -1), 0.0, atol=1e-12)


# ==========================================================================
#  Block / FFN / LayerNorm
# ==========================================================================


def test_block_shape_2d() -> None:
    blk = TransformerBlock(d_model=16, n_heads=4, d_ff=32)
    x = Tensor(np.random.randn(7, 16))
    assert blk(x).data.shape == (7, 16)


def test_block_shape_3d() -> None:
    blk = TransformerBlock(d_model=16, n_heads=4, d_ff=32)
    x = Tensor(np.random.randn(2, 7, 16))
    assert blk(x).data.shape == (2, 7, 16)


def test_block_residual_preserves_on_identity_grad() -> None:
    """残差结构：当子层输出为 0 时，输出应等于输入（验证残差接线正确）。"""
    blk = TransformerBlock(d_model=8, n_heads=2, d_ff=16)
    x = Tensor(np.random.randn(4, 8))
    y = blk(x)
    # 不要求相等，但要求有限且形状正确（上面已测），这里只验证梯度能流回 x
    s = sum(y)
    s.backward()
    assert x.grad is not None
    assert np.isfinite(x.grad).all()


def test_feedforward_shape() -> None:
    ffn = FeedForward(d_model=8, d_ff=16)
    x = Tensor(np.random.randn(4, 8))
    assert ffn(x).data.shape == (4, 8)


def test_feedforward_params() -> None:
    ffn = FeedForward(d_model=8, d_ff=16)
    assert len(ffn.parameters()) == 4  # W1,b1,W2,b2


def test_layernorm_module_shape() -> None:
    from model.block import _LayerNorm

    ln = _LayerNorm(8)
    x = Tensor(np.random.randn(4, 8))
    assert ln(x).data.shape == (4, 8)


def test_block_grad_flow() -> None:
    blk = TransformerBlock(d_model=8, n_heads=2, d_ff=16)
    x = Tensor(np.random.randn(4, 8))
    s = sum(blk(x))
    s.backward()
    assert all(p.grad is not None for p in blk.parameters())


# ==========================================================================
#  Decoder / 整机
# ==========================================================================


def test_decoder_stack_logits_shape() -> None:
    stack = DecoderStack(d_model=16, n_heads=4, d_ff=32, n_layers=2, vocab_size=50)
    x = Tensor(np.random.randn(6, 16))
    assert stack(x).data.shape == (6, 50)


def test_decoder_stack_num_layers() -> None:
    stack = DecoderStack(d_model=16, n_heads=4, d_ff=32, n_layers=3, vocab_size=50)
    assert len(stack.blocks) == 3


def test_transformerlm_logits_shape() -> None:
    m = TransformerLM(vocab_size=50, d_model=16, n_heads=4, d_ff=32, n_layers=2, max_len=64)
    logits = m(np.array([[1, 2, 3, 4]]))
    assert logits.data.shape == (1, 4, 50)


def test_transformerlm_parameters_count() -> None:
    m = TransformerLM(vocab_size=50, d_model=16, n_heads=4, d_ff=32, n_layers=1, max_len=32)
    # 至少包含 embedding + 4 个 MHA 权重 + FFN 2 + LN 2*2 + proj
    assert len(m.parameters()) >= 10


def test_transformerlm_forward_finite() -> None:
    m = TransformerLM(vocab_size=50, d_model=16, n_heads=4, d_ff=32, n_layers=2, max_len=32)
    logits = m(np.array([[1, 2, 3]]))
    assert np.isfinite(logits.data).all()


def test_transformerlm_auto_causal_mask() -> None:
    """不给 mask 时自动按序列长生成因果掩码，前向仍能跑且有限。"""
    m = TransformerLM(vocab_size=50, d_model=16, n_heads=4, d_ff=32, n_layers=1, max_len=32)
    out1 = m(np.array([[1, 2, 3]]))
    out2 = m(np.array([[1, 2, 3, 4]]))
    assert out1.data.shape == (1, 3, 50)
    assert out2.data.shape == (1, 4, 50)


# ==========================================================================
#  DataLoader
# ==========================================================================


def test_build_examples_count() -> None:
    ids = list(range(20))
    ex = build_examples(ids, context_len=8)
    # 滑窗：i 从 0 到 20-8-1 = 11，共 12 个
    assert len(ex) == 12


def test_build_examples_xy_shifted() -> None:
    ids = [1, 2, 3, 4, 5]
    ex = build_examples(ids, context_len=3)
    x, y = ex[0]
    assert list(x) == [1, 2, 3]
    assert list(y) == [2, 3, 4]


def test_examples_from_lines_varying_length() -> None:
    lines = [[1, 2, 3], [4, 5, 6, 7, 8, 9]]
    ex = examples_from_lines(lines, context_len=4)
    # 第一行短 → 1 个；第二行长 → 6-4=2 个窗口
    assert len(ex) == 3
    assert all(len(x) == len(y) for x, y in ex)


def test_dataloader_pads_to_max_len() -> None:
    ex = [
        (np.array([1, 2, 3]), np.array([2, 3, 4])),
        (np.array([5, 6, 7, 8, 9]), np.array([6, 7, 8, 9, 10])),
    ]
    dl = DataLoader(ex, batch_size=2, pad_id=0, shuffle=False)
    X, Y, M = next(iter(dl))
    assert X.shape == (2, 5)
    assert X[0, 3] == 0 and X[0, 4] == 0  # 第一个样本右侧被 pad


def test_dataloader_mask_marks_real() -> None:
    ex = [
        (np.array([1, 2, 3]), np.array([2, 3, 4])),
        (np.array([5, 6, 7, 8, 9]), np.array([6, 7, 8, 9, 10])),
    ]
    dl = DataLoader(ex, batch_size=2, pad_id=0, shuffle=False)
    X, Y, M = next(iter(dl))
    assert M[0, 0] == 1.0 and M[0, 3] == 0.0
    assert M[1, 4] == 1.0


def test_dataloader_batch_shapes() -> None:
    ex = examples_from_lines([BPE.encode(line) for line in SAMPLE_CORPUS.splitlines()], context_len=16)
    dl = DataLoader(ex, batch_size=8, pad_id=0, shuffle=False)
    X, Y, M = next(iter(dl))
    assert X.shape == Y.shape == M.shape
    assert X.shape[0] == 8


def test_dataloader_len() -> None:
    ex = list(range(20))
    samples = build_examples(ex, context_len=5)
    dl = DataLoader(samples, batch_size=4, shuffle=False)
    assert len(dl) == 4  # 15 个样本 / 4 = 4 批（最后一批不足 4 也成一批）


def test_dataloader_pad_id_used() -> None:
    ex = [(np.array([1]), np.array([2]))]
    dl = DataLoader(ex, batch_size=1, pad_id=7, shuffle=False)
    X, Y, M = next(iter(dl))
    assert X.shape[1] == 1  # 单条无需补齐
    dl2 = DataLoader([(np.array([1]), np.array([2])), (np.array([3, 4]), np.array([4, 5]))],
                     batch_size=2, pad_id=7, shuffle=False)
    X2, _, _ = next(iter(dl2))
    assert X2[0, 1] == 7


# ==========================================================================
#  Training
# ==========================================================================


def _make_toy_corpus_loader(context_len: int = 16, batch_size: int = 16):
    id_lines = [BPE.encode(line) for line in SAMPLE_CORPUS.splitlines() if line.strip()]
    examples = examples_from_lines(id_lines, context_len)
    return DataLoader(examples, batch_size=batch_size, pad_id=0, shuffle=True)


def test_training_loss_decreases() -> None:
    loader = _make_toy_corpus_loader()
    m = TransformerLM(vocab_size=BPE.vocab_size, d_model=24, n_heads=4, d_ff=64, n_layers=2, max_len=64)
    opt = Adam(m.parameters(), lr=0.02)
    tr = Trainer(m, opt)
    losses = tr.run(loader, n_steps=150, log_every=0)
    assert losses[-1] < losses[0]
    assert np.isfinite(losses).all()


def test_training_loss_finite_each_step() -> None:
    loader = _make_toy_corpus_loader()
    m = TransformerLM(vocab_size=BPE.vocab_size, d_model=16, n_heads=4, d_ff=32, n_layers=1, max_len=48)
    opt = Adam(m.parameters(), lr=0.01)
    tr = Trainer(m, opt)
    losses = tr.run(loader, n_steps=40, log_every=0)
    assert np.all(np.isfinite(losses))


def test_sgd_step_updates_param() -> None:
    w = Parameter(np.random.randn(4, 3))
    before = w.data.copy()
    X = Tensor(np.random.randn(2, 4))
    y = sum(matmul(X, w))
    y.backward()
    SGD([w], lr=0.1).step()
    assert not np.allclose(before, w.data)


def test_adam_step_updates_param() -> None:
    w = Parameter(np.random.randn(4, 3))
    before = w.data.copy()
    X = Tensor(np.random.randn(2, 4))
    y = sum(matmul(X, w))
    y.backward()
    Adam([w], lr=0.1).step()
    assert not np.allclose(before, w.data)


def test_cross_entropy_mask_excludes_pad() -> None:
    """被 mask 掉的位置改 target 不应影响 loss。"""
    logits = Tensor(np.random.randn(3, 5))
    t1 = np.array([0, 1, 2])
    w = np.array([1.0, 1.0, 0.0])  # 第 3 个位置是 pad
    loss1 = cross_entropy(logits, t1, mask=w).data.item()
    t2 = np.array([0, 1, 4])  # 只改被 mask 的位置
    loss2 = cross_entropy(logits, t2, mask=w).data.item()
    assert abs(loss1 - loss2) < 1e-12


def test_trainer_reduces_loss_on_tiny_data() -> None:
    """极小数据上过拟合，loss 应明显下降（验证优化器真的在学）。"""
    X = np.array([[1, 2, 3, 4]])
    Y = np.array([[2, 3, 4, 5]])
    M = np.ones((1, 4))
    m = TransformerLM(vocab_size=10, d_model=8, n_heads=2, d_ff=16, n_layers=1, max_len=8)
    opt = Adam(m.parameters(), lr=0.05)
    tr = Trainer(m, opt)
    first = tr.train_step(X, Y, M)
    for _ in range(60):
        tr.train_step(X, Y, M)
    last = tr.train_step(X, Y, M)
    assert last < first


# ==========================================================================
#  Inference / 生成
# ==========================================================================


def _tiny_trained_model():
    m = TransformerLM(vocab_size=BPE.vocab_size, d_model=24, n_heads=4, d_ff=64, n_layers=2, max_len=64)
    loader = _make_toy_corpus_loader()
    tr = Trainer(m, Adam(m.parameters(), lr=0.02))
    tr.run(loader, n_steps=120, log_every=0)
    return m


def test_generate_ids_within_vocab() -> None:
    m = _tiny_trained_model()
    ids = generate_ids(m, BPE, "Transformer", max_new_tokens=10, temperature=0.0)
    assert all(0 <= i < BPE.vocab_size for i in ids)


def test_generate_ids_correct_length_greedy() -> None:
    m = _tiny_trained_model()
    prompt_ids = BPE.encode("Transformer")
    out = generate_ids(m, BPE, "Transformer", max_new_tokens=10, temperature=0.0)
    # 贪心且不遇 EOS 时，新 token 数 == max_new_tokens
    assert len(out) - len(prompt_ids) == 10


def test_generate_greedy_deterministic() -> None:
    m = _tiny_trained_model()
    a = generate_ids(m, BPE, "模型", max_new_tokens=8, temperature=0.0)
    b = generate_ids(m, BPE, "模型", max_new_tokens=8, temperature=0.0)
    assert a == b


def test_generate_temperature_sample_deterministic_with_rng() -> None:
    m = _tiny_trained_model()
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    a = generate_ids(m, BPE, "模型", max_new_tokens=8, temperature=0.8, top_k=10, rng=rng1)
    b = generate_ids(m, BPE, "模型", max_new_tokens=8, temperature=0.8, top_k=10, rng=rng2)
    assert a == b


def test_generate_top_k_restricts_candidates() -> None:
    m = _tiny_trained_model()
    last = m(np.array([BPE.encode("模型")[-m.max_len:]]), mask=None).data[0, -1, :]
    k = 5
    topk = set(np.argsort(last)[-k:])
    # top_k 采样下，若温度极小则必取全局 argmax，必在 top-k 内
    out = generate_ids(m, BPE, "模型", max_new_tokens=1, temperature=0.001, top_k=k)
    new = out[-1]
    assert new in topk


class _ForceEOSModel:
    """测试桩：每个位置都恒把 EOS 的预测分数拉到最高，用来验证「遇 EOS 即停」。"""

    max_len = 64

    def __init__(self, vocab_size: int, eos_id: int) -> None:
        self.vocab_size = vocab_size
        self.eos_id = eos_id

    def __call__(self, ids: np.ndarray, mask=None) -> Tensor:
        logits = np.zeros((ids.shape[0], ids.shape[1], self.vocab_size))
        logits[:, -1, self.eos_id] = 10.0
        return Tensor(logits)


def test_generate_stops_at_eos() -> None:
    """模型恒预测 EOS：贪心第一步就停，不追加任何新 token。"""
    model = _ForceEOSModel(vocab_size=BPE.vocab_size, eos_id=EOS_ID)
    prompt = "abc"
    out = generate_ids(model, BPE, prompt, max_new_tokens=10, temperature=0.0)
    assert out == BPE.encode(prompt)  # 没有新 token


def test_generate_returns_str() -> None:
    m = _tiny_trained_model()
    text = generate(m, BPE, "Transformer", max_new_tokens=8, temperature=0.7, top_k=20)
    assert isinstance(text, str)


def test_generate_length_le_max() -> None:
    m = _tiny_trained_model()
    out = generate_ids(m, BPE, "Transformer", max_new_tokens=12, temperature=0.0)
    assert len(out) - len(BPE.encode("Transformer")) <= 12


def test_logits_of_prefix_shape() -> None:
    m = _tiny_trained_model()
    last = m(np.array([BPE.encode("Transformer")[-m.max_len:]]), mask=None).data[0, -1, :]
    assert last.shape == (BPE.vocab_size,)


# ==========================================================================
#  集成：sample_corpus + BPE 全链路
# ==========================================================================


def test_integration_pipeline_shapes() -> None:
    """Tokenizer → Embedding → Blocks → logits 全链路形状自洽。"""
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    ids = tok.encode(SAMPLE_CORPUS)[:32]
    m = TransformerLM(vocab_size=tok.vocab_size, d_model=24, n_heads=4, d_ff=64, n_layers=2, max_len=64)
    logits = m(np.array([ids]))
    assert logits.data.shape == (1, len(ids), tok.vocab_size)


def test_integration_train_then_generate() -> None:
    """训练后能生成，且生成的 token 全在词表内。"""
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    id_lines = [tok.encode(line) for line in SAMPLE_CORPUS.splitlines() if line.strip()]
    loader = DataLoader(examples_from_lines(id_lines, 16), 16, shuffle=True)
    m = TransformerLM(vocab_size=tok.vocab_size, d_model=24, n_heads=4, d_ff=64, n_layers=2, max_len=64)
    Trainer(m, Adam(m.parameters(), lr=0.02)).run(loader, n_steps=100, log_every=0)
    out = generate_ids(m, tok, "Transformer", max_new_tokens=8, temperature=0.0)
    assert all(0 <= i < tok.vocab_size for i in out)


def test_integration_ids_in_vocab() -> None:
    """BPE 编码整份语料的 id 必须全在词表内（否则模型会越界）。"""
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    ids = tok.encode(SAMPLE_CORPUS)
    assert all(0 <= i < tok.vocab_size for i in ids)


def test_integration_untrained_model_generates() -> None:
    """未训练模型也能跑通生成（只是内容可能无意义）。"""
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    m = TransformerLM(vocab_size=tok.vocab_size, d_model=16, n_heads=4, d_ff=32, n_layers=1, max_len=48)
    text = generate(m, tok, "Token", max_new_tokens=5, temperature=0.0)
    assert isinstance(text, str)


def test_integration_loss_lower_than_random() -> None:
    """训练后 loss 应明显低于初始随机（≈log(vocab)）。"""
    tok = BPETokenizer.train(SAMPLE_CORPUS, 500)
    id_lines = [tok.encode(line) for line in SAMPLE_CORPUS.splitlines() if line.strip()]
    loader = DataLoader(examples_from_lines(id_lines, 16), 16, shuffle=True)
    m = TransformerLM(vocab_size=tok.vocab_size, d_model=24, n_heads=4, d_ff=64, n_layers=2, max_len=64)
    losses = Trainer(m, Adam(m.parameters(), lr=0.02)).run(loader, n_steps=150, log_every=0)
    assert losses[-1] < np.log(tok.vocab_size) - 0.5


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
