"""完全离线、确定性的规则化答案评分。"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class AutoEvalScore:
    total: float
    keyword_coverage: float
    format_compliance: float
    length_reasonableness: float
    faithfulness_proxy: float
    repetition_score: float

    def to_dict(self) -> dict:
        return asdict(self)


def _terms(text: str) -> set[str]:
    lowered = (text or "").casefold()
    ascii_terms = set(re.findall(r"[a-z][a-z0-9_+.-]{1,}", lowered))
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", lowered))
    chinese_terms = {chinese[i : i + 2] for i in range(max(0, len(chinese) - 1))}
    return ascii_terms | chinese_terms


def derive_keywords(reference: str, limit: int = 8) -> list[str]:
    chunks = [part.strip() for part in re.split(r"[，。；：、（）()]+", reference or "")]
    candidates = [part for part in chunks if 2 <= len(part) <= 24]
    if not candidates:
        candidates = sorted(_terms(reference), key=lambda item: (-len(item), item))
    return candidates[:limit]


def keyword_coverage(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0 if answer.strip() else 0.0
    text = answer.casefold()
    return sum(keyword.casefold() in text for keyword in keywords) / len(keywords)


def format_compliance(answer: str) -> float:
    text = answer.strip()
    if not text:
        return 0.0
    score = 0.35
    if re.search(r"[。！？.!?]", text):
        score += 0.25
    if re.search(r"(^|\n)\s*(?:[-*]|\d+[.)、]|[①②③④⑤])", text):
        score += 0.25
    if "\n" in text or re.search(r"[：:；;]", text):
        score += 0.15
    return min(1.0, score)


def length_reasonableness(answer: str, reference: str = "", min_chars: int = 20, max_chars: int = 500) -> float:
    n = len(answer.strip())
    if n == 0:
        return 0.0
    if reference.strip():
        target = max(1, len(reference.strip()))
        ratio = n / target
        if 0.6 <= ratio <= 1.6:
            return 1.0
        if ratio < 0.6:
            return max(0.0, ratio / 0.6)
        return max(0.0, 1.0 - (ratio - 1.6) / 2.4)
    if n < min_chars:
        return n / min_chars
    if n <= max_chars:
        return 1.0
    return max(0.0, 1.0 - (n - max_chars) / max_chars)


def repetition_score(answer: str, ngram: int = 3) -> float:
    compact = re.sub(r"\s+", "", answer)
    if not compact:
        return 0.0
    if len(compact) < ngram:
        return 1.0
    grams = [compact[i : i + ngram] for i in range(len(compact) - ngram + 1)]
    return len(set(grams)) / len(grams)


def faithfulness_proxy(answer: str, reference: str) -> float:
    if not answer.strip() or not reference.strip():
        return 0.0
    answer_terms = _terms(answer)
    reference_terms = _terms(reference)
    if not answer_terms:
        return 0.0
    return len(answer_terms & reference_terms) / len(answer_terms)


def evaluate_answer(answer: str, reference: str = "", keywords: "list[str] | None" = None) -> AutoEvalScore:
    keys = list(keywords) if keywords is not None else derive_keywords(reference)
    coverage = keyword_coverage(answer, keys)
    fmt = format_compliance(answer)
    length = length_reasonableness(answer, reference)
    faithful = faithfulness_proxy(answer, reference)
    repeat = repetition_score(answer)
    total = 100.0 * (0.40 * coverage + 0.15 * fmt + 0.15 * length + 0.20 * faithful + 0.10 * repeat)
    return AutoEvalScore(
        total=float(total), keyword_coverage=float(coverage), format_compliance=float(fmt),
        length_reasonableness=float(length), faithfulness_proxy=float(faithful),
        repetition_score=float(repeat),
    )


def aggregate_scores(scores: list[AutoEvalScore]) -> dict:
    if not scores:
        raise ValueError("scores 不能为空")
    fields = tuple(AutoEvalScore.__dataclass_fields__)
    return {field: float(np.mean([getattr(score, field) for score in scores])) for field in fields} | {
        "n": len(scores)
    }


def rank_answers(candidates: dict[str, list[str]], references: list[str], keywords: "list[list[str]] | None" = None) -> list[dict]:
    rows = []
    for name, answers in candidates.items():
        if len(answers) != len(references):
            raise ValueError(f"{name} 的答案数与 reference 数不一致")
        scores = [
            evaluate_answer(answer, references[i], None if keywords is None else keywords[i])
            for i, answer in enumerate(answers)
        ]
        rows.append({"model": name, **aggregate_scores(scores)})
    return sorted(rows, key=lambda row: (-row["total"], row["model"]))


__all__ = [
    "AutoEvalScore", "aggregate_scores", "derive_keywords", "evaluate_answer",
    "faithfulness_proxy", "format_compliance", "keyword_coverage",
    "length_reasonableness", "rank_answers", "repetition_score",
]
