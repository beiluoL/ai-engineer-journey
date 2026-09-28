"""内置离线语料 —— 手写的小型中英混排文本，训练 tokenizer 用。

为什么自己写而不是去下载：
本项目有一条硬约束 —— **不联网下载任何语料**。而且一份 1KB 量级、
术语高度重复的语料，反而比一本小说更适合讲清楚 BPE：合并次数有限、
每次合并都能追溯到具体哪两个符号、词表增长看得见。

中英混排是刻意设计的一半英文一半中文：英文让 BPE 有机会学到
``trans + former`` 这类子词，中文让字符级的「一字一 token」和 BPE 的
「二字词合并」形成直接对比。
"""

from __future__ import annotations

SAMPLE_CORPUS = """\
Transformer 是一种神经网络架构，它在 2017 年被提出，现在几乎所有大模型都用它。
大模型的第一步是 Tokenization，也就是把文本切成 token。
token 是模型能看懂的最小单位，一个 token 不一定是完整的词。
英文里 token 常常是子词，比如 transformer 可能被切成 trans 和 former 两段。
中文里一个 token 常常是一个字，也可能是一个常用的二字词。
词表 vocab 决定了 Embedding 矩阵有多少行，词表越大，Embedding 参数越多。
Embedding 把每个 token 的 id 映射成一个向量，向量的维度叫 d_model。
模型还需要位置编码 positional encoding，否则 Attention 看不出词的前后顺序。
Attention 注意力机制让每个 token 自己去问：我应该重点看哪些 token？
Self-Attention 的计算是 Q 乘 K 的转置，除以根号 d_k，再 softmax，最后乘 V。
多头注意力 Multi-Head Attention 把 d_model 切成 h 份，每份各自算一次 Attention。
Transformer Block 由多头注意力、残差连接、LayerNorm 和前馈网络 FFN 组成。
FFN 先把维度放大四倍，过一个 GELU 激活，再压回 d_model。
Decoder-Only 模型只保留 Decoder，用因果掩码 causal mask 挡住未来的 token。
训练时我们做自回归：用前 n 个 token 预测第 n+1 个 token。
损失函数用交叉熵 cross entropy，优化器用 AdamW，学习率要 warmup 再衰减。
推理时模型一个 token 一个 token 地采样，采样策略有 greedy、top-k 和 temperature。
温度 temperature 越高，分布越平，生成越随机；温度越低，生成越确定。
上下文长度 context length 决定模型一次能看多少 token，Attention 复杂度是 O(n^2)。
Batch 训练要把句子补齐到同样长度，补齐的位置用 pad token 并且不计入 loss。
BOS 表示句子开始，EOS 表示句子结束，UNK 表示词表里没有的字符。
字符级分词器简单但序列长，BPE 分词器能把高频片段并成一个 token，序列更短。
BPE 的训练只有一句话：反复合并出现次数最多的相邻符号，直到词表达到 vocab_size。
训练完之后要把 vocab 和 merges 一起保存，推理时必须用同一份 merges 才能对齐。
本项目从 Tokenizer 开始，然后做 Embedding、Transformer Block、训练循环和推理。
"""

#: 展示用的一句话：中文 + 英文 + 数字 + 标点全都有，且**不在** SAMPLE_CORPUS 里，
#: 用来演示「词表里没有的字符会落到 <unk>」这件事。
MIXED_TEXT = "GPT-4 在 2023 年发布，参数量约 1.8T，中文支持也不错。"
