# 10 · 术语表：中英文对照与简明定义

> 按主题分 8 组，每条给出**中文名 · 英文名 · 一句话定义 · 详见章节**。
> 遇到不认识的词，先在这里定位，再回对应章节看原理。

---

## A · 数据表示与分词

| 中文 | 英文 | 定义 | 详见 |
|------|------|------|------|
| 词元 / 标记 | **token** | 模型处理文本的最小单位，介于字符与词之间；可能是一个词、半个词或几个字符 | [01](01-basics-language-model.md) |
| 分词 / 切词 | **tokenization** | 把文本切分成 token 序列的过程 | [01](01-basics-language-model.md) |
| 分词器 | **tokenizer** | 执行分词的程序，含词表与合并规则 | [01](01-basics-language-model.md) |
| 词表 | **vocabulary / vocab** | 所有 token 的集合，大小决定 embedding 与输出层参数量 | [01](01-basics-language-model.md) |
| 字节对编码 | **BPE**（Byte-Pair Encoding） | 通过反复合并最高频相邻符号对来构建子词词表 | [01](01-basics-language-model.md) |
| 子词 | **subword** | 比词小、比字符大的单位，BPE 的产物 | [01](01-basics-language-model.md) |
| 词元嵌入 | **token embedding** | token id 查表得到的向量表示 | [01](01-basics-language-model.md) |
| 嵌入 / 向量表示 | **embedding** | 把离散对象映射为连续向量的表示（广义）；也指整段文本的向量（RAG 用） | [01](01-basics-language-model.md) |
| 位置编码 | **positional encoding / PE** | 把位置信息注入模型的手段 | [03](03-transformer.md) |
| 旋转位置编码 | **RoPE**（Rotary Position Embedding） | 通过旋转 Q/K 使内积只依赖相对位置 | [09](09-math-foundations.md) |
| 特殊标记 | **special token** | BOS / EOS / PAD / 角色标记等控制用 token | [01](01-basics-language-model.md) |
| 对话模板 | **chat template** | 把系统提示、用户、助手消息拼成模型训练时见过的格式 | [01](01-basics-language-model.md) |
| 序列长度 | **sequence length / context length** | 一次处理的 token 数上限 | [07](07-decoding-and-inference.md) |
| 上下文窗口 | **context window** | 模型能"看到"的最大 token 数 | [07](07-decoding-and-inference.md) |
| 字节级 BPE | **BBPE**（Byte-level BPE） | 在字节上做 BPE，保证任何 Unicode 文本都不 OOV | [01](01-basics-language-model.md) |

---

## B · 模型结构

| 中文 | 英文 | 定义 | 详见 |
|------|------|------|------|
| 变换器 | **Transformer** | 基于自注意力构建的序列建模架构 | [03](03-transformer.md) |
| 自注意力 | **self-attention** | 同一序列内部各位置相互加权的机制 | [02](02-attention.md) |
| 查询 / 键 / 值 | **Query / Key / Value (QKV)** | 注意力的三种角色：发起检索、被检索、被加权取值 | [02](02-attention.md) |
| 多头注意力 | **MHA**（Multi-Head Attention） | 把 d_model 切分给多个头并行做注意力 | [02](02-attention.md) |
| 多查询注意力 | **MQA**（Multi-Query Attention） | 所有头共享一份 K/V，大幅省 KV Cache | [02](02-attention.md) |
| 分组查询注意力 | **GQA**（Grouped-Query Attention） | 头分组共享 K/V，MHA 与 MQA 的折中（当前主流） | [02](02-attention.md) |
| 前馈网络 | **FFN / MLP** | 每个 token 独立经过的两层（或三层）网络，占约 2/3 参数 | [03](03-transformer.md) |
| 激活函数 | **activation**（ReLU / GELU / SwiGLU） | 引入非线性的函数；SwiGLU 是当前主流 | [03](03-transformer.md) |
| 残差连接 | **residual connection** | `x + f(x)`，保证梯度能跨层回传 | [03](03-transformer.md) |
| 层归一化 | **LayerNorm / RMSNorm** | 对特征维做归一化；RMSNorm 省去均值计算 | [03](03-transformer.md) |
| 前置/后置归一化 | **Pre-LN / Post-LN** | 归一化放子层前还是后；Pre-LN 是深层训练稳定的关键 | [03](03-transformer.md) |
| 自回归 | **autoregressive** | 逐 token 生成，每步以已生成内容为条件 | [01](01-basics-language-model.md) |
| 因果掩码 | **causal mask** | 屏蔽未来位置，保证生成时不"偷看"答案 | [02](02-attention.md) |
| 编码器 / 解码器 | **encoder / decoder** | 双向理解模块 / 因果生成模块 | [03](03-transformer.md) |
| 仅解码器 | **decoder-only** | 只有解码器堆叠的架构，当前 LLM 主流 | [03](03-transformer.md) |
| 隐藏维度 | **d_model / hidden size** | 每层表示的向量维度 | [03](03-transformer.md) |
| 头维度 | **d_head** | d_model / n_heads | [02](02-attention.md) |
| 混合专家 | **MoE**（Mixture of Experts） | 用多个 FFN 专家 + 路由，每 token 只激活少数 | [03](03-transformer.md) |
| 总参数 / 激活参数 | **total / active parameters** | 模型全部参数 / 每个 token 实际参与计算的参数 | [03](03-transformer.md) |

---

## C · 训练与预训练

| 中文 | 英文 | 定义 | 详见 |
|------|------|------|------|
| 预训练 | **pretraining** | 在海量无标注文本上做下一 token 预测 | [04](04-pretraining.md) |
| 基础模型 | **base model / foundation model** | 预训练完、尚未指令微调的模型 | [04](04-pretraining.md) |
| 因果语言建模 | **CLM**（Causal LM） | 目标为预测下一个 token | [04](04-pretraining.md) |
| 掩码语言建模 | **MLM**（Masked LM） | 挖掉部分 token 让模型填空（BERT 式） | [04](04-pretraining.md) |
| 中间填充 | **FIM**（Fill-in-the-Middle） | 用前缀+后缀预测中间内容，代码补全必备 | [04](04-pretraining.md) |
| 对数几率 / 未归一化打分 | **logits** | 过 softmax 之前的原始输出分数 | [01](01-basics-language-model.md) |
| 归一化指数函数 | **softmax** | 把任意实数向量变成概率分布 | [01](01-basics-language-model.md) |
| 交叉熵损失 | **cross-entropy loss** | `-log p(正确token)`，语言模型的标准目标 | [01](01-basics-language-model.md) |
| 困惑度 | **perplexity (PPL)** | 交叉熵的指数，等价于"在几个候选里犹豫" | [01](01-basics-language-model.md) |
| 教师强制 | **teacher forcing** | 训练时用真实前缀而非模型自己生成的 token | [01](01-basics-language-model.md) |
| 曝光偏差 | **exposure bias** | 训练见真实前缀、推理见自己输出造成的不一致 | [01](01-basics-language-model.md) |
| 缩放定律 | **scaling law** | 损失随参数量/数据量呈幂律下降的规律 | [06](06-scaling-and-emergence.md) |
| 计算最优 | **compute-optimal** | 给定算力下参数与数据的最优配比（Chinchilla: D≈20N） | [06](06-scaling-and-emergence.md) |
| 过度训练 | **overtraining** | 为降低推理成本而刻意多训 token | [06](06-scaling-and-emergence.md) |
| 涌现能力 | **emergent ability** | 规模跨过阈值后才出现的能力 | [06](06-scaling-and-emergence.md) |
| 上下文学习 | **ICL**（In-Context Learning） | 不改权重，靠提示里的示例学会任务 | [06](06-scaling-and-emergence.md) |
| 思维链 | **CoT**（Chain-of-Thought） | 先输出推理步骤再给结论 | [06](06-scaling-and-emergence.md) |
| 数据并行 | **DP / DDP** | 每卡完整模型、各喂不同数据 | [04](04-pretraining.md) |
| 张量并行 | **TP** | 把层内矩阵切开分到多卡 | [04](04-pretraining.md) |
| 流水线并行 | **PP** | 不同层放不同卡，micro-batch 流水 | [04](04-pretraining.md) |
| 专家并行 | **EP** | MoE 专家分散到不同卡 | [04](04-pretraining.md) |
| 零冗余优化 / 全分片数据并行 | **ZeRO / FSDP** | 把优化器状态、梯度、参数分片存放 | [04](04-pretraining.md) |
| 梯度检查点 | **gradient checkpointing** | 不存中间激活，反向时重算以省显存 | [04](04-pretraining.md) |
| 梯度裁剪 | **gradient clipping** | 限制梯度范数，防止训练爆炸 | [09](09-math-foundations.md) |
| 混合精度 | **mixed precision**（FP16 / BF16 / FP8） | 用低位宽加速计算；BF16 因范围大而更适合训练 | [04](04-pretraining.md) |
| 学习率预热 | **warmup** | 训练初期逐步升高学习率 | [04](04-pretraining.md) |
| 损失尖峰 | **loss spike** | 训练中损失突然飙升，通常需回滚或裁剪 | [04](04-pretraining.md) |
| 优化器 | **AdamW** | LLM 训练的标准优化器（解耦权重衰减） | [09](09-math-foundations.md) |
| 批量大小 | **batch size** | 一次更新使用的样本/token 数 | [04](04-pretraining.md) |

---

## D · 微调与参数高效方法

| 中文 | 英文 | 定义 | 详见 |
|------|------|------|------|
| 微调 | **fine-tuning (FT)** | 在预训练模型上继续训练以适配任务 | [05](05-finetuning.md) |
| 全量微调 | **full fine-tuning** | 更新全部参数，显存开销最大 | [05](05-finetuning.md) |
| 监督微调 / 指令微调 | **SFT**（Supervised Fine-Tuning） | 用指令-回答对做监督训练 | [05](05-finetuning.md) |
| 参数高效微调 | **PEFT** | 只训练极少量新增/选定参数的微调方法总称 | [05](05-finetuning.md) |
| 低秩适配 | **LoRA**（Low-Rank Adaptation） | 冻结原权重，只学低秩增量 ΔW = BA | [05](05-finetuning.md) |
| 量化 LoRA | **QLoRA** | 4bit 量化基座 + LoRA，单卡可微调大模型 | [05](05-finetuning.md) |
| 秩 | **rank (r)** | LoRA 中低秩矩阵的中间维度，控制容量 | [05](05-finetuning.md) |
| 缩放系数 | **lora_alpha** | 控制 LoRA 增量的缩放，影响有效学习率 | [05](05-finetuning.md) |
| 冻结 | **freeze** | 不更新某部分参数 | [05](05-finetuning.md) |
| 适配器 | **adapter** | 层间插入的小型可训练模块（已边缘化） | [05](05-finetuning.md) |
| 前缀微调 / 提示微调 | **prefix / prompt tuning** | 只训练序列前的虚拟 token | [05](05-finetuning.md) |
| 灾难性遗忘 | **catastrophic forgetting** | 微调窄任务后通用能力退化 | [05](05-finetuning.md) |
| 过拟合 | **overfitting** | 在训练集上表现好、泛化差 | [05](05-finetuning.md) |
| 损失掩码 | **loss mask** | 只对回答部分计算损失 | [05](05-finetuning.md) |
| 检索增强生成 | **RAG**（Retrieval-Augmented Generation） | 先检索外部知识再生成，用于注入事实 | [05](05-finetuning.md) |
| 蒸馏 | **distillation** | 用大模型（教师）训练小模型（学生） | [07](07-decoding-and-inference.md) |

---

## E · 对齐与安全

| 中文 | 英文 | 定义 | 详见 |
|------|------|------|------|
| 对齐 | **alignment** | 让模型行为符合人类意图与价值 | [08](08-alignment-rlhf.md) |
| 基于人类反馈的强化学习 | **RLHF** | SFT → 奖励模型 → RL 三阶段的对齐方法 | [08](08-alignment-rlhf.md) |
| 奖励模型 | **reward model (RM)** | 学会给人偏好排序打分的模型 | [08](08-alignment-rlhf.md) |
| 奖励劫持 | **reward hacking** | 模型学会骗奖励分数而非真正变好 | [08](08-alignment-rlhf.md) |
| 近端策略优化 | **PPO** | RLHF 中使用的强化学习算法 | [08](08-alignment-rlhf.md) |
| 直接偏好优化 | **DPO**（Direct Preference Optimization） | 无需奖励模型的偏好优化，损失形似监督学习 | [08](08-alignment-rlhf.md) |
| 组相对策略优化 | **GRPO** | 去掉 critic，用组内相对比较估优势 | [08](08-alignment-rlhf.md) |
| AI 反馈强化学习 | **RLAIF** | 用 AI 而非人类生成偏好标注 | [08](08-alignment-rlhf.md) |
| 宪法式 AI | **Constitutional AI** | 让模型按一套原则自我批判与修正 | [08](08-alignment-rlhf.md) |
| 参考模型 | **reference model** | 对齐时冻结的原模型，用于 KL 约束 | [08](08-alignment-rlhf.md) |
| KL 惩罚 | **KL penalty** | 限制新模型偏离参考模型的强度 | [08](08-alignment-rlhf.md) |
| 谄媚 | **sycophancy** | 迎合用户错误观点的行为倾向 | [08](08-alignment-rlhf.md) |
| 幻觉 | **hallucination** | 生成看似合理但事实错误的内容 | [01](01-basics-language-model.md) |
| 红队测试 | **red teaming** | 主动寻找模型漏洞与有害输出 | [08](08-alignment-rlhf.md) |

---

## F · 推理与部署

| 中文 | 英文 | 定义 | 详见 |
|------|------|------|------|
| 推理 | **inference** | 用训练好的模型做前向计算 | [07](07-decoding-and-inference.md) |
| 预填充 | **prefill** | 并行处理整个 prompt、填充 KV Cache 的阶段 | [07](07-decoding-and-inference.md) |
| 解码阶段 | **decode** | 逐 token 生成的阶段，受显存带宽限制 | [07](07-decoding-and-inference.md) |
| KV 缓存 | **KV Cache** | 缓存历史 token 的 K/V，避免每步重算 | [07](07-decoding-and-inference.md) |
| 分页注意力 | **PagedAttention** | 像操作系统分页一样管理 KV，消除碎片（vLLM） | [07](07-decoding-and-inference.md) |
| 前缀缓存 | **prefix cache** | 复用相同系统提示的 KV | [07](07-decoding-and-inference.md) |
| 连续批处理 | **continuous batching** | 每步迭代重新组批，完成的请求立刻换新请求 | [07](07-decoding-and-inference.md) |
| 解码策略 | **decoding strategy** | greedy / beam / top-k / top-p 等采样方式 | [07](07-decoding-and-inference.md) |
| 温度 | **temperature** | 缩放 logits 控制分布平坦度 | [01](01-basics-language-model.md) |
| 核采样 | **top-p / nucleus sampling** | 在累计概率达 p 的最小集合内采样 | [07](07-decoding-and-inference.md) |
| 重复惩罚 | **repetition penalty** | 降低已出现 token 的概率，抑制复读 | [07](07-decoding-and-inference.md) |
| 投机解码 | **speculative decoding** | 用小模型草拟、大模型验证，加速生成 | [07](07-decoding-and-inference.md) |
| 量化 | **quantization** | 用低位宽表示权重/激活以省显存 | [07](07-decoding-and-inference.md) |
| 训练后量化 | **PTQ** | 训练完成后量化，需校准数据（GPTQ/AWQ） | [07](07-decoding-and-inference.md) |
| 首 token 延迟 | **TTFT**（Time To First Token） | 从请求到第一个 token 的时间 | [07](07-decoding-and-inference.md) |
| 每 token 延迟 | **TPOT / ITL** | 相邻输出 token 之间的时间间隔 | [07](07-decoding-and-inference.md) |
| 吞吐量 | **throughput** | 单位时间产出的 token 数 | [07](07-decoding-and-inference.md) |
| 流式输出 | **streaming** | 边生成边返回，改善体感延迟 | [07](07-decoding-and-inference.md) |
| 预填充-解码分离 | **PD disaggregation** | prefill 与 decode 部署在不同实例 | [07](07-decoding-and-inference.md) |

---

## G · 评测与指标

| 中文 | 英文 | 定义 | 详见 |
|------|------|------|------|
| 基准测试 | **benchmark** | 标准化评测集，如 MMLU、GSM8K、HumanEval | [06](06-scaling-and-emergence.md) |
| 数据污染 | **data contamination** | 评测集内容混入训练数据导致分数虚高 | [04](04-pretraining.md) |
| 精确匹配 | **exact match (EM)** | 答案完全一致才算对（不连续指标） | [06](06-scaling-and-emergence.md) |
| 困惑度 | **perplexity** | 语言拟合程度指标 | [01](01-basics-language-model.md) |
| 胜率 | **win rate** | 与基线两两比较的胜出比例 | [08](08-alignment-rlhf.md) |
| 人工评估 | **human evaluation** | 人类对输出质量的判断，最终准绳 | [08](08-alignment-rlhf.md) |
| 大模型裁判 | **LLM-as-a-judge** | 用强模型给输出打分，便宜但需验证 | [08](08-alignment-rlhf.md) |
| 拒绝率 / 过度拒绝 | **over-refusal** | 把正常请求也拒掉的比例 | [08](08-alignment-rlhf.md) |

---

## H · 生态与工具

| 中文 | 英文 | 定义 | 详见 |
|------|------|------|------|
| 模型卡 / 权重 | **model card / weights** | 模型说明文件与参数文件（safetensors 等） | [11](11-open-source-projects.md) |
| 哈根脸 | **Hugging Face (HF)** | 最大的模型与数据集托管平台 | [11](11-open-source-projects.md) |
| 参数高效微调库 | **PEFT**（HF 库名） | LoRA 等方法的官方实现库 | [11](11-open-source-projects.md) |
| 变换器库 | **Transformers** | HF 的模型加载与推理基础库 | [11](11-open-source-projects.md) |
| 强化学习库 | **TRL** | HF 的 SFT / DPO / PPO 训练库 | [11](11-open-source-projects.md) |
| 推理引擎 | **inference engine**（vLLM / SGLang / TGI） | 高吞吐的服务化部署框架 | [11](11-open-source-projects.md) |
| 服务化 | **serving** | 把模型包装成 API 服务的过程 | [07](07-decoding-and-inference.md) |
| 智能体 | **agent** | 让模型自主调用工具、多步执行的系统 | — |
| 工具调用 | **function / tool calling** | 模型输出结构化调用请求，由外部执行 | — |
| 上下文协议 | **MCP**（Model Context Protocol） | 标准化模型与外部工具的连接协议 | — |

---

## 快速区分：最容易混的六组

| 一组词 | 区别一句话 |
|--------|------------|
| 预训练 vs 微调 | 预训练学语言（几 T～几十 T token，无标注）；微调学任务（几千～百万条，有标注） |
| embedding vs logits | embedding 在**输入侧**（token→向量）；logits 在**输出侧**（向量→打分） |
| LayerNorm vs BatchNorm | LN 对**每个 token 的特征维**归一化（与 batch 无关）；BN 依赖 batch 统计 |
| MHA vs GQA vs MQA | 差别只在 **K/V 头数**：各自独立 / 分组共享 / 全部共享 |
| RLHF vs DPO | RLHF 要 4 个模型 + 在线 RL；DPO 只要 2 个模型 + 离线偏好对 |
| 量化 vs 蒸馏 vs 剪枝 | 降低精度 / 大教小重新训 / 删结构。只有量化不改结构 |

---

[← 上一章：数学基础](09-math-foundations.md) · [返回总览](README.md) · [下一章：开源项目推荐 →](11-open-source-projects.md)
