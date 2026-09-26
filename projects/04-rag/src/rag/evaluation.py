"""RAG 三段式评估（对应 milestone 10）。

RAG 链路是三段接力，整体效果差时必须能定位是哪一段出了问题：

    第一段 检索质量：Hit Rate@k / MRR        —— 零成本，纯规则
    第二段 上下文质量：context_hit_rate      —— 零成本，纯规则
    第三段 生成质量：keyword / refusal       —— 确定性子集；忠实度需要 LLM Judge（进阶）

不看分段指标就调参，等于蒙着眼睛拧螺丝：Hit Rate 低说明该改检索层（换 embedding、
调 chunk 策略），改 prompt 措辞毫无用处；Hit Rate 高但答案错，说明资料找对了模型
却在自由发挥，该改 system 规则。

    口径纪律（10 坑 4）：EvalReport 的字段就是口径，评测集文件入库固定，
    对比只允许「同口径、同评测集」的前后对照。

    忠实度单独放在本节末尾：它是「生成质量」的定性子集，需要真实模型才谈得上。
"""

from __future__ import annotations

from .llm import _split_sentences, parse_answer_refs

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class EvalCase:
    """一条评测案例。黄金标准来自文档本身，不需要人工写答案。"""

    question: str
    expected_source: str                # 答案应该在的文档
    expected_keywords: tuple[str, ...] = ()
    should_refuse: bool = False         # True = 知识库里没有，应拒答


@dataclass
class EvalReport:
    """评估报告。字段即口径，前后对比只看同一结构的两份报告。"""

    n_cases: int = 0
    hit_rate_at_3: float = 0.0
    hit_rate_at_5: float = 0.0
    mrr: float = 0.0
    context_hit_rate: float = 0.0       # 正确文档是否被装进最终 prompt
    keyword_pass_rate: float = 0.0      # 关键词出现在答案中的比例（非拒答案例）
    refusal_pass_rate: float = 0.0      # 该拒答的案例正确拒答的比例
    failed_cases: list[str] = field(default_factory=list)

    def dump(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2),
                        encoding="utf-8")

    @classmethod
    def load(cls, path: Path | str) -> "EvalReport":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        failed = data.pop("failed_cases", [])
        return cls(**data, failed_cases=failed)

    def summary(self) -> str:
        return (f"n={self.n_cases}  hit@3={self.hit_rate_at_3:.3f}  "
                f"hit@5={self.hit_rate_at_5:.3f}  mrr={self.mrr:.3f}  "
                f"ctx={self.context_hit_rate:.3f}  kw={self.keyword_pass_rate:.3f}  "
                f"refuse={self.refusal_pass_rate:.3f}")


def _source_name(source: str) -> str:
    """metadata 里的 source 是路径，统一取文件名比对，避免路径前缀口径问题（10 坑 2）。"""
    return Path(source).name if source else ""


def evaluate(service, eval_cases: list[EvalCase], budget: int | None = None) -> EvalReport:
    """跑一遍评测集，返回确定性指标 + 失败明细。

    评估只依赖 RAGService 的公开接口（ask() 返回的 RAGAnswer），内部零件是黑盒。
    """
    hits3 = hits5 = ctx_hits = kw_pass = ref_pass = 0
    rr_sum = 0.0
    failed: list[str] = []

    for i, case in enumerate(eval_cases):
        answer = service.ask(case.question, budget)
        sources = [_source_name(s) for s in answer.retrieved_sources]

        # —— 第一段：检索质量 ——
        ranks = [j + 1 for j, s in enumerate(sources) if s == _source_name(case.expected_source)]
        if ranks:
            rr_sum += 1.0 / ranks[0]
            hits5 += 1
            if ranks[0] <= 3:
                hits3 += 1
        elif not case.should_refuse:
            # 拒答案例的 expected_source 只是占位符（知识库里本来就没有这份文档），
            # 检索没命中是**预期内**的，不该混进失败明细里当噪声。
            failed.append(f"#{i} 未命中 [{_source_name(case.expected_source)}]: {case.question}")

        # —— 第二段：上下文质量（正确文档有没有装进最终 prompt）——
        cited = {_source_name(c.source) for c in answer.citations}
        if _source_name(case.expected_source) in cited:
            ctx_hits += 1

        # —— 第三段：生成质量（确定性子集：拒答 + 关键词）——
        if case.should_refuse:
            if "没有相关资料" in answer.answer:
                ref_pass += 1
            else:
                failed.append(f"#{i} 应拒答却作答: {case.question}")
        else:
            missing = [k for k in case.expected_keywords if k not in answer.answer]
            if not missing:
                kw_pass += 1
            else:
                failed.append(f"#{i} 缺关键词 {missing}: {case.question}")

    n = len(eval_cases)
    n_normal = sum(1 for c in eval_cases if not c.should_refuse)
    n_refuse = n - n_normal
    return EvalReport(
        n_cases=n,
        hit_rate_at_3=hits3 / n if n else 0.0,
        hit_rate_at_5=hits5 / n if n else 0.0,
        mrr=rr_sum / n if n else 0.0,
        context_hit_rate=ctx_hits / n if n else 0.0,
        keyword_pass_rate=kw_pass / max(n_normal, 1),
        refusal_pass_rate=ref_pass / max(n_refuse, 1),
        failed_cases=failed,
    )


# --------------------------------------------------------------------------
# 忠实度审计（12 章：接真实模型之后才需要它）
# --------------------------------------------------------------------------
# FakeLLMClient 只会复制参考资料里的句子，忠实度天然是 100%。
# 换成真实模型，「模型答得像不像资料里的」就变成一个必须量化的问题 ——
# 否则一次坏答案只能靠人工看，无法进 CI。

_CJK_RE = re.compile(r"[一-鿿]")
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DIGIT_RE = re.compile(r"\d+(?:[.,]\d+)*")

# 虚词表：中文里「的 / 了 / 是」这类字几乎必然与资料重合，留在分母里会把
# 覆盖率稀释成 1.0，让审计结果失去区分度（12 章实测：不匹配虚词前，
# 一句纯编造的话也能拿到 0.97 的重合率）。
_STOPWORDS = frozenset(
    "的了是在和与就都而被这那有为以从对中把将并及或于之所很更最也还只"
    "一二三上下可以我们能你会他它们个什么怎么可以应该需要以及或者但是"
    "然后还有不是不个点点充到相当用降存占内优方案原".split())


def _token_set(text: str) -> set[str]:
    return set(_CJK_RE.findall(text)) | {w.lower() for w in _WORD_RE.findall(text)}


def _content_tokens(text: str) -> set[str]:
    """去掉虚词之后的实词集合，才是真正能用来判依据的部分。"""
    return {t for t in _token_set(text) if t not in _STOPWORDS}


def _strong_tokens(text: str) -> set[str]:
    """数字 + 英文标识符：这类词编不出来，一旦在资料里找不到就是强信号。"""
    return set(_DIGIT_RE.findall(text)) | {w.lower() for w in _WORD_RE.findall(text)}


@dataclass(frozen=True)
class FaithfulnessReport:
    """一句话一句判「这句话有没有依据」。

    ratio 是「有依据句子 / 全部句子」，不是「重合词占比」——
    后者会被一句idez halluziation 里的常见词刷高，前者更能反映真实风险。
    """

    n_sentences: int = 0
    n_supported: int = 0
    unsupported: list[str] = field(default_factory=list)
    ratio: float = 0.0
    cites_nothing: bool = False        # 答案里一个 [n] 都没标 → 根本没法溯源

    def summary(self) -> str:
        return (f"句子 {self.n_sentences} 句，有依据 {self.n_supported} 句，"
                f"无出处 {len(self.unsupported)} 句，"
                f"忠实度 {self.ratio:.2f}"
                + ("，且未标注引用编号" if self.cites_nothing else ""))


def check_faithfulness(answer: str, context_text: str,
                       min_hit_ratio: float = 0.7,
                       min_tokens: int = 3,
                       min_strong_ratio: float = 0.5) -> FaithfulnessReport:
    """逐句核对答案是否能在【参考资料】里找到依据。

    两条判据，任一不过就记为「无出处」：

        1. 强词判据：句中的数字 / 英文标识符，命中资料的比例 >= min_strong_ratio。
           编造最容易发生在细节上（"降到 3.14 MB""占比 12.7%"），这些数字编得
           非常合理，光看覆盖率抓不到。实测踩过的坑：语料里恰好提到过一次 "MB"
           和 "3.13"，于是「至少一个命中」的判据被一句话绕过；改成比例才拦得住。
        2. 实词覆盖率：去掉虚词后的实词命中率 >= min_hit_ratio，且命中数 >= min_tokens。

    判据取「词面重合」而非「语义等价」：这是零成本的粗筛（不用再调一次 LLM），
    目的是把「明显编造」的样本捞出来进人工复核，不是给模型打分。
    """
    ctx_tokens = _token_set(context_text)
    ctx_strong = _strong_tokens(context_text)
    ctx_content = _content_tokens(context_text)
    unsupported: list[str] = []
    n_supported = 0
    sentences = [s for s in _split_sentences(answer or "") if s]
    for sent in sentences:
        strong = _strong_tokens(sent)
        if strong and len(strong & ctx_strong) / len(strong) < min_strong_ratio:
            unsupported.append(sent)         # 编出来的数字/术语，资料里多半没有
            continue
        toks = _content_tokens(sent)
        hit = len(toks & ctx_content)
        if hit >= min_tokens and hit / max(len(toks), 1) >= min_hit_ratio:
            n_supported += 1
        else:
            unsupported.append(sent)

    return FaithfulnessReport(
        n_sentences=len(sentences),
        n_supported=n_supported,
        unsupported=unsupported,
        ratio=n_supported / len(sentences) if sentences else 0.0,
        cites_nothing=not parse_answer_refs(answer),
    )


def check_answer_faithfulness(answer, **kw) -> FaithfulnessReport:
    """从一个 RAGAnswer 直接出忠实度报告（复用它留档的 system_prompt）。"""
    return check_faithfulness(answer.answer, answer.system_prompt, **kw)


def check_expected_sources(eval_cases: list[EvalCase], indexed_sources: list[str]) -> list[str]:
    """程序自检评测集：每条 expected_source 必须真实存在于索引里（10 坑 2）。

    返回有问题的案例描述列表；空列表 = 评测集可信。
    """
    names = {_source_name(s) for s in indexed_sources}
    return [f"#{i} expected_source 不在索引中: {c.expected_source} ({c.question})"
            for i, c in enumerate(eval_cases)
            if not c.should_refuse and c.expected_source != "*"
            and _source_name(c.expected_source) not in names]


def build_default_eval_cases() -> list[EvalCase]:
    """开箱即用的评测集（覆盖正常案例 + 拒答边界）。

    对应 data/ 下 5 个语料文件的真实内容；替换成自己的知识库时同步改这里。
    """
    return [
        EvalCase(
            question="生成器为什么能省内存？",
            expected_source="data/python-generators.md",
            expected_keywords=("yield", "惰性", "内存"),
        ),
        EvalCase(
            question="装饰器是怎么给函数加功能的？",
            expected_source="data/python-decorators.md",
            expected_keywords=("闭包", "functools.wraps", "参数"),
        ),
        EvalCase(
            question="GIL 对多线程 CPU 密集任务有什么影响？",
            expected_source="data/python-gil.md",
            expected_keywords=("GIL", "CPU 密集", "多进程"),
        ),
        EvalCase(
            question="token 和字符换算大概是什么比例？",
            expected_source="data/llm-tokenization.md",
            expected_keywords=("4", "字符"),
        ),
        EvalCase(
            question="temperature 设成 0 会怎么样？",
            expected_source="data/llm-sampling.txt",
            expected_keywords=("贪心", "确定性"),
        ),
        EvalCase(
            question="RAG 里向量检索和关键词检索各自擅长什么？",
            expected_source="data/llm-retrieval.md",
            expected_keywords=("语义", "专有名词"),
        ),
        EvalCase(
            question="今天上海天气怎么样？",
            expected_source="nonexistent.md",
            should_refuse=True,
        ),
    ]
