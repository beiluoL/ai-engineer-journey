"""可观测性：把「系统现在健康吗」从一个感觉变成一组能回答的数字（milestone 15）。

RAG 上线后最先被问到的三个问题，都不是「功能对不对」，而是：

    1. 慢在哪？    —— 检索、精排、组装、生成，四段各占多少毫秒
    2. 召回有没有退化？ —— 相似度分数的分布有没有整体左移
    3. 钱花在哪？    —— embedding / LLM 各调了多少次，失败了多少次

这三个问题光看日志答不上来：日志是**逐条的事件**，而这三个是**聚合的分布**。
所以这里做一个进程内的指标注册表——不是 Prometheus，只是一层薄的计数 + 采样：

    MetricsRegistry：线程安全的 counter / timing / score 三种样本
    MeteredEmbeddingClient / MeteredLLMClient：装饰器，包在真实客户端外面计数

为什么用装饰器而不是把埋点写进 embedding.py / llm.py？
    因为「计量」和「怎么调模型」是两件事。写死进去会让 `OpenAICompatibleLLMClient`
    同时承担协议适配和统计两个职责，测试时还要想办法关掉统计。包一层则完全
    不影响原有行为：不包就是原来的客户端，包一层才计量。

单位约定：**内部一律存秒**（SI 基准，不会算错），出报告时才转成毫秒。
早期版本直接存毫秒，结果改一处取秒、一处取毫秒，p99 差了 1000 倍还没人发现。
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .embedding import BaseEmbeddingClient
from .llm import BaseLLMClient


class Names:
    """指标名唯一事实源。

    散在各处的裸字符串迟早会写出两个同名不同义的 `llm.latency`
    （一个含重试、一个不含），到那时对比图表就是在比两件不同的事。
    """

    # —— 请求级 ——
    REQUESTS = "rag.requests"                 # 问答请求数（含拒答）
    REFUSALS = "rag.refusals"                 # 检索为空直接拒答的次数
    REQUEST_LATENCY = "rag.request.latency"   # 端到端：进 ask() 到返回

    # —— 分段耗时（一次请求内四段，加起来≈端到端）——
    RETRIEVE_LATENCY = "rag.retrieve.latency"
    RERANK_LATENCY = "rag.rerank.latency"
    ASSEMBLE_LATENCY = "rag.assemble.latency"
    # pipeline 记的是「这一趟生成总共花了多久」（语义 3 重试两次就记两次）；
    GENERATE_LATENCY = "rag.generate.latency"

    # —— 召回质量 ——
    RETRIEVE_SCORE = "rag.retrieve.score"     # 进 prompt 前的相似度分数分布
    RETRIEVE_FILTERED = "rag.retrieve.filtered"  # 被 min_score 拦掉的条数

    # —— 外部调用（花钱的地方）——
    EMBED_CALLS = "embedding.calls"
    EMBED_TEXTS = "embedding.texts"           # 累计送进去的文本条数（批量×批大小）
    EMBED_LATENCY = "embedding.latency"
    EMBED_ERRORS = "embedding.errors"

    LLM_CALLS = "llm.calls"
    # 单次 LLM 调用的耗时（不含重试、不含拼装）；要「含重试」的看上面那个
    LLM_LATENCY = "llm.latency"
    LLM_CHUNKS = "llm.chunks"                 # 流式产出的帧数
    LLM_ERRORS = "llm.errors"


# 分数分桶边界：与 settings.min_score 默认 0.2 对齐，第一桶就是「会被拦掉的那批」
SCORE_BUCKETS: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.01)


def percentile(values: list[float], q: float) -> float:
    """线性插值分位数。q ∈ [0, 1]。

    不用 nearest-rank：样本少（比如只有 3 次调用）时它只会给出已有的某个值，
    p90 会等于 max，看着像「每次都最慢」。插值在样本少时更诚实。
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


@dataclass(frozen=True)
class Summary:
    """一组样本的统计摘要。unit 只是渲染时用的标签（ms / score）。"""

    name: str = ""
    count: int = 0
    mean: float = 0.0
    p50: float = 0.0
    p90: float = 0.0
    p99: float = 0.0
    min: float = 0.0
    max: float = 0.0
    unit: str = ""

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ("name", "count", "mean", "p50", "p90", "p99", "min", "max", "unit")}


def summarize(name: str, values: list[float], unit: str = "") -> Summary:
    if not values:
        return Summary(name=name, unit=unit)
    return Summary(
        name=name, count=len(values), unit=unit,
        mean=sum(values) / len(values),
        p50=percentile(values, 0.50),
        p90=percentile(values, 0.90),
        p99=percentile(values, 0.99),
        min=min(values), max=max(values),
    )


def bucketize(values: Iterable[float],
              edges: tuple[float, ...] = SCORE_BUCKETS) -> list[tuple[str, int]]:
    """把分数切成桶。返回 [(桶标签, 条数), ...]。

    分布比均值有用：均值 0.45 可能是「全都 0.45」，也可能是「一半 0.9 一半 0.0」，
    后者意味着一半的召回其实是噪声，只是被 top_k 补齐掩盖了。
    """
    counts = [0] * (len(edges) - 1)
    for v in values:
        for i in range(len(edges) - 1):
            if edges[i] <= v < edges[i + 1]:
                counts[i] += 1
                break
    labels = []
    for i in range(len(edges) - 1):
        hi = edges[i + 1]
        labels.append((f"[{edges[i]:.2f}, {hi if hi > 1 else hi:.2f})", counts[i]))
    return labels


class MetricsRegistry:
    """进程内指标注册表。

    线程安全是硬要求：Web API 里 `/ask` 是 `asyncio.to_thread` 跑的，
    同一时刻可能有多个请求在记指标；字典的 `+=` 不是原子操作，
    不加锁会在压测时丢计数（丢的是「调用次数」这种最不该丢的数）。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._timings: dict[str, list[float]] = defaultdict(list)
        self._scores: dict[str, list[float]] = defaultdict(list)

    # —— 写入 ——
    def inc(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            self._counters[name] += value

    def observe(self, name: str, seconds: float) -> None:
        with self._lock:
            self._timings[name].append(seconds)

    def observe_scores(self, name: str, scores: Iterable[float]) -> None:
        values = [float(s) for s in scores]
        if values:
            with self._lock:
                self._scores[name].extend(values)

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        """分段计时。异常也会记（慢的往往是失败的那次），但不吞异常。"""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - t0)

    # —— 读取 ——
    def counter(self, name: str) -> float:
        with self._lock:
            return self._counters.get(name, 0.0)

    def snapshot(self) -> dict:
        """一次一致的快照。逐字段单独读会让「请求数」和「耗时数」来自不同时刻。"""
        with self._lock:
            counters = dict(self._counters)
            timings = {k: list(v) for k, v in self._timings.items()}
            scores = {k: list(v) for k, v in self._scores.items()}
        return {
            "counters": counters,
            "timings": {k: summarize(k, v, unit="ms").to_dict()
                        for k, v in timings.items()},
            "scores": {k: summarize(k, v, unit="score").to_dict()
                       for k, v in scores.items()},
            "score_buckets": {k: bucketize(v) for k, v in scores.items()},
        }

    def save(self, path: str | Path, meta: Mapping | None = None) -> Path:
        """把快照落盘，供**另一个进程**回读对比（15 → 16 章的跨进程需求）。

        为什么不存原始样本：一次压测几万条耗时样本全写进去，文件能到几 MB，
        而对比只需要分位数。摘要是「够用的最小集合」，也避免把单条请求数据
        （可能含业务信息）落到盘上。
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "meta": dict(meta or {}),
            "snapshot": self.snapshot(),
        }
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return p

    @staticmethod
    def load(path: str | Path) -> dict:
        """读回 save() 写下的文件；返回带 saved_at / meta / snapshot 的 dict。"""
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._timings.clear()
            self._scores.clear()


# --------------------------------------------------------------------------
# 报告渲染
# --------------------------------------------------------------------------

def _fmt(v: float, width: int = 8) -> str:
    return f"{v:>{width}.2f}"


def render_report(snapshot: Mapping) -> str:
    """把快照渲染成终端能直接看的文本。

    报告存在的意义是**让人一眼看出异常**，所以除了统计值还带一句判读：
    比如拒答率超过一半、p99 是 p50 的十倍，这些比表格本身更重要。
    """
    lines: list[str] = []
    counters: dict = snapshot.get("counters", {})
    timings: dict = snapshot.get("timings", {})
    scores: dict = snapshot.get("scores", {})
    buckets: dict = snapshot.get("score_buckets", {})

    lines.append("── 计数器 ────────────────────────────────────────")
    if not counters:
        lines.append("  （无）")
    for key in sorted(counters):
        lines.append(f"  {key:<28}{counters[key]:>10.0f}")

    if counters.get(Names.REQUESTS):
        req = counters[Names.REQUESTS]
        ref = counters.get(Names.REFUSALS, 0.0)
        lines.append(f"  → 拒答率 {ref / req:.1%}"
                     + ("（超过一半，先查语料覆盖度而不是调 prompt）" if ref / req > 0.5 else ""))

    lines.append("")
    lines.append("── 耗时（ms）──────────────────────────────────────")
    if timings:
        lines.append(f"  {'指标':<26}{'次数':>5}{'均值':>9}{'p50':>9}"
                     f"{'p90':>9}{'p99':>9}{'最大':>9}")
        for key in sorted(timings):
            s = timings[key]
            lines.append(f"  {key:<26}{s['count']:>5}"
                         f"{_fmt(s['mean'] * 1000, 9)}{_fmt(s['p50'] * 1000, 9)}"
                         f"{_fmt(s['p90'] * 1000, 9)}{_fmt(s['p99'] * 1000, 9)}"
                         f"{_fmt(s['max'] * 1000, 9)}")
        # 判读：p99 远大于 p50 说明抖动，而不是「系统慢」
        for key in sorted(timings):
            s = timings[key]
            if s["p50"] > 0 and s["p99"] / s["p50"] > 5:
                lines.append(f"  → {key} 的 p99 是 p50 的 {s['p99'] / s['p50']:.1f} 倍："
                             f"是抖动（个别请求慢），不是整体慢，别按均值去扩容")
                break
    else:
        lines.append("  （无）")

    lines.append("")
    lines.append("── 召回分数分布 ───────────────────────────────────")
    if scores:
        for key in sorted(scores):
            s = scores[key]
            lines.append(f"  {key}: n={s['count']} 均值 {s['mean']:.3f} "
                         f"p50 {s['p50']:.3f} 最低 {s['min']:.3f} 最高 {s['max']:.3f}")
            for label, n in buckets.get(key, []):
                bar = "█" * min(n, 40)
                lines.append(f"      {label:<16}{n:>4}  {bar}")
        for key in sorted(buckets):
            rows = buckets[key]
            if rows:
                total = sum(n for _, n in rows) or 1
                low = rows[0][1] / total
                lines.append(f"  → 落在最低桶（<0.2，会被 min_score 拦掉）的占 {low:.1%}")
    else:
        lines.append("  （无）")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# 跨进程对比
# --------------------------------------------------------------------------

# 对比只看这几个：它们是「变慢了 / 变贵了 / 变笨了」的直接证据。
# 全量对比会把 n=1 的样本也算进去，那些波动没有意义，只会淹没真信号。
DIFF_METRICS: tuple[tuple[str, str], ...] = (
    (Names.REQUEST_LATENCY, "p50"),
    (Names.REQUEST_LATENCY, "p90"),
    (Names.RETRIEVE_LATENCY, "p50"),
    (Names.GENERATE_LATENCY, "p50"),
    (Names.LLM_LATENCY, "p50"),
    (Names.EMBED_LATENCY, "p50"),
)

DIFF_COUNTERS: tuple[str, ...] = (
    Names.REQUESTS, Names.REFUSALS, Names.LLM_CALLS,
    Names.EMBED_CALLS, Names.LLM_ERRORS,
)


def render_diff(baseline: Mapping, current: Mapping,
                tolerance: float = 0.20) -> str:
    """把两次运行的快照并排对比。baseline / current = save() 读回的 dict。

    判读规则：耗时类恶化超过 tolerance（默认 20%）才报警。为什么不设得更严？
    真实 LLM 的 p50 本身就有 ±15% 的抖动（14 章实测同一问题连问 5 次有 4 种答案），
    阈值低于抖动幅度只会天天误报 —— 报警要报在噪声之上。

    对比的是**比率不是绝对值**：两次运行的问题数可能不同，所以计数器一律
    折算成「每次请求」再比，否则问 6 题和问 20 题的调用次数根本没有可比性。
    """
    base_snap = baseline.get("snapshot", baseline)
    curr_snap = current.get("snapshot", current)
    lines: list[str] = []
    lines.append(f"基线 {baseline.get('saved_at', '?')}   meta={baseline.get('meta', {})}")
    lines.append(f"当前 {current.get('saved_at', '?')}   meta={current.get('meta', {})}")
    lines.append("")
    lines.append(f"{'指标（耗时 ms）':<34}{'基线':>10}{'当前':>10}{'变化':>10}   判读")
    lines.append("-" * 76)

    warnings: list[str] = []
    for name, stat in DIFF_METRICS:
        b = base_snap.get("timings", {}).get(name, {})
        c = curr_snap.get("timings", {}).get(name, {})
        # 快照内部存秒（render_report 里也是渲染时才 ×1000），这里同样要换算，
        # 否则表里的 0.25 会被当成 250ms 之外的另一个量纲。
        bv, cv = float(b.get(stat, 0.0)) * 1000, float(c.get(stat, 0.0)) * 1000
        if not bv and not cv:
            continue
        delta = (cv - bv) / bv if bv else 0.0
        verdict = "持平"
        if bv and delta > tolerance:
            verdict = f"⚠ 变慢 {delta:.0%}"
            warnings.append(f"{name} {stat} 恶化 {delta:.0%}")
        elif bv and delta < -tolerance:
            verdict = f"✅ 变快 {-delta:.0%}"
        lines.append(f"{name + ' ' + stat:<34}{bv:>10.1f}{cv:>10.1f}"
                     f"{delta:>+9.0%}   {verdict}")

    b_req = float(base_snap.get("counters", {}).get(Names.REQUESTS, 0.0))
    c_req = float(curr_snap.get("counters", {}).get(Names.REQUESTS, 0.0))
    for name in DIFF_COUNTERS:
        b_raw = float(base_snap.get("counters", {}).get(name, 0.0))
        c_raw = float(curr_snap.get("counters", {}).get(name, 0.0))
        bv = b_raw / b_req if b_req else b_raw
        cv = c_raw / c_req if c_req else c_raw
        delta = (cv - bv) / bv if bv else 0.0
        verdict = "持平"
        if bv and abs(delta) > tolerance:
            verdict = f"{'⚠ 变高' if delta > 0 else '✅ 变低'} {abs(delta):.0%}"
            if delta > 0 and name in (Names.LLM_ERRORS, Names.REFUSALS):
                warnings.append(f"{name}/请求 上升 {delta:.0%}")
        lines.append(f"{name + ' /请求':<34}{bv:>10.2f}{cv:>10.2f}"
                     f"{delta:>+9.0%}   {verdict}")

    lines.append("")
    if warnings:
        lines.append("⚠ 需要关注：" + "；".join(warnings))
    else:
        lines.append("✅ 无指标恶化超过 "
                     f"{tolerance:.0%}（低于这个幅度通常是真实抖动，不是回归）")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 计量包装器
# --------------------------------------------------------------------------

class MeteredEmbeddingClient(BaseEmbeddingClient):
    """包一层 embedding 客户端：记调用次数、批大小、耗时、失败数。

    失败也要记耗时：超时的那次往往是最慢的，只记成功会把 p99 洗得很好看。
    """

    def __init__(self, inner: BaseEmbeddingClient,
                 registry: MetricsRegistry | None = None) -> None:
        self._inner = inner
        self.registry = registry or MetricsRegistry()

    @property
    def inner(self) -> BaseEmbeddingClient:
        """被包住的原客户端。要断言「到底用了哪个实现」时穿透这一层。"""
        return self._inner

    @property
    def model_name(self) -> str:            # type: ignore[override]
        return self._inner.model_name

    @property
    def dim(self) -> int:                   # type: ignore[override]
        return self._inner.dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.registry.inc(Names.EMBED_CALLS)
        self.registry.inc(Names.EMBED_TEXTS, len(texts))
        t0 = time.perf_counter()
        try:
            return await self._inner.embed(texts)
        except Exception:
            self.registry.inc(Names.EMBED_ERRORS)
            raise
        finally:
            self.registry.observe(Names.EMBED_LATENCY, time.perf_counter() - t0)


class MeteredLLMClient(BaseLLMClient):
    """包一层 LLM 客户端：记调用次数、耗时、流式帧数、失败数。

    chat() 与 iter_tokens() 分开计数没有意义（都是一次生成），
    但 iter_tokens 要额外记帧数：帧数过少说明「流式」其实在攒批吐。
    """

    def __init__(self, inner: BaseLLMClient,
                 registry: MetricsRegistry | None = None) -> None:
        self._inner = inner
        self.registry = registry or MetricsRegistry()

    @property
    def inner(self) -> BaseLLMClient:
        """被包住的原客户端（同上）。"""
        return self._inner

    @property
    def model_name(self) -> str:            # type: ignore[override]
        return self._inner.model_name

    def chat(self, messages: list[dict]) -> str:
        self.registry.inc(Names.LLM_CALLS)
        t0 = time.perf_counter()
        try:
            return self._inner.chat(messages)
        except Exception:
            self.registry.inc(Names.LLM_ERRORS)
            raise
        finally:
            self.registry.observe(Names.LLM_LATENCY, time.perf_counter() - t0)

    def iter_tokens(self, messages: list[dict]) -> Iterator[str]:
        self.registry.inc(Names.LLM_CALLS)
        t0 = time.perf_counter()
        try:
            for token in self._inner.iter_tokens(messages):
                if token:
                    self.registry.inc(Names.LLM_CHUNKS)
                yield token
        except Exception:
            self.registry.inc(Names.LLM_ERRORS)
            raise
        finally:
            self.registry.observe(Names.LLM_LATENCY, time.perf_counter() - t0)
