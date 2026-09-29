"""无泄漏、可分层的 Java 面试评估集构建。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EvalSplit:
    train: list[dict]
    heldout: list[dict]
    report: dict


def normalize_instruction(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold().strip()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def infer_topic(record: dict) -> str:
    text = f"{record.get('instruction', '')} {record.get('output', '')}".lower()
    groups = [
        ("并发", ("线程", "锁", "volatile", "cas", "aqs", "concurrent", "atomic")),
        ("JVM", ("jvm", "gc", "垃圾", "内存", "类加载", "oom", "引用")),
        ("集合", ("hashmap", "arraylist", "linkedlist", "集合", "string", "泛型")),
        ("Spring", ("spring", "bean", "ioc", "aop", "transactional")),
        ("数据与网络", ("mysql", "redis", "索引", "缓存", "http", "事务")),
    ]
    for topic, words in groups:
        if any(word in text for word in words):
            return topic
    return "Java 基础"


def length_stratum(record: dict) -> str:
    size = len((record.get("instruction") or "").strip())
    if size <= 18:
        return "短"
    if size <= 30:
        return "中"
    return "长"


def record_stratum(record: dict) -> str:
    return f"{infer_topic(record)}/{length_stratum(record)}"


def deduplicate_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    unique: list[dict] = []
    duplicates: list[dict] = []
    seen: set[str] = set()
    for record in records:
        key = normalize_instruction(record.get("instruction", ""))
        if not key or key in seen:
            duplicates.append(record)
            continue
        seen.add(key)
        unique.append(dict(record))
    return unique, duplicates


def leakage_report(train: list[dict], heldout: list[dict]) -> dict:
    train_keys = {normalize_instruction(r.get("instruction", "")) for r in train}
    heldout_keys = {normalize_instruction(r.get("instruction", "")) for r in heldout}
    overlap = sorted((train_keys & heldout_keys) - {""})
    return {
        "train_size": len(train),
        "heldout_size": len(heldout),
        "overlap_count": len(overlap),
        "overlap_keys": overlap,
        "leakage_free": not overlap,
    }


def _stratified_pick(records: list[dict], size: int, seed: int) -> list[dict]:
    if size < 0 or size > len(records):
        raise ValueError(f"heldout_size={size} 超出可选记录数 {len(records)}")
    rng = np.random.default_rng(seed)
    buckets: dict[str, list[dict]] = {}
    for record in records:
        buckets.setdefault(record_stratum(record), []).append(record)
    for values in buckets.values():
        rng.shuffle(values)
    names = sorted(buckets)
    rng.shuffle(names)
    selected: list[dict] = []
    while len(selected) < size:
        progressed = False
        for name in names:
            if buckets[name] and len(selected) < size:
                selected.append(buckets[name].pop())
                progressed = True
        if not progressed:
            break
    return selected


def stratum_counts(records: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for record in records:
        key = record_stratum(record)
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def build_evaluation_set(
    records: list[dict],
    heldout_size: int,
    seed: int = 0,
    training_records: "list[dict] | None" = None,
) -> EvalSplit:
    """去重后分层抽取 held-out；可额外排除已用于训练的 instruction。"""
    unique, duplicates = deduplicate_records(records)
    external_keys = {
        normalize_instruction(r.get("instruction", "")) for r in (training_records or [])
    }
    candidates = [
        record for record in unique
        if normalize_instruction(record.get("instruction", "")) not in external_keys
    ]
    excluded = len(unique) - len(candidates)
    heldout = _stratified_pick(candidates, heldout_size, seed)
    heldout_keys = {normalize_instruction(r.get("instruction", "")) for r in heldout}
    if training_records is None:
        train = [r for r in unique if normalize_instruction(r.get("instruction", "")) not in heldout_keys]
    else:
        train = list(training_records)
    leak = leakage_report(train, heldout)
    report = {
        "input_size": len(records),
        "unique_size": len(unique),
        "duplicates_removed": len(duplicates),
        "excluded_by_training": excluded,
        "train_size": len(train),
        "heldout_size": len(heldout),
        "train_strata": stratum_counts(train),
        "heldout_strata": stratum_counts(heldout),
        **leak,
    }
    if not report["leakage_free"]:
        raise RuntimeError(f"评估集泄漏：发现 {report['overlap_count']} 条 instruction 重叠")
    return EvalSplit(train=train, heldout=heldout, report=report)


__all__ = [
    "EvalSplit", "build_evaluation_set", "deduplicate_records", "infer_topic",
    "leakage_report", "length_stratum", "normalize_instruction", "record_stratum",
    "stratum_counts",
]
