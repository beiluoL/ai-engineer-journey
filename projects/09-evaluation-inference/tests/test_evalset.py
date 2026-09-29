from __future__ import annotations

import pytest

from ie.evalset import (
    build_evaluation_set,
    deduplicate_records,
    infer_topic,
    leakage_report,
    length_stratum,
    normalize_instruction,
)


def records(n=30):
    topics = ["HashMap", "volatile线程", "JVM垃圾回收", "Spring Bean", "MySQL索引"]
    return [
        {"instruction": f"请解释 {topics[i % len(topics)]} 原理 {i}", "input": "", "output": f"答案 {i}。"}
        for i in range(n)
    ]


@pytest.mark.parametrize("size", list(range(1, 13)))
def test_heldout_size_and_no_overlap(size):
    split = build_evaluation_set(records(), heldout_size=size, seed=0)
    assert len(split.heldout) == size
    assert len(split.train) == 30 - size
    assert split.report["leakage_free"]


@pytest.mark.parametrize("seed", [0, 1, 2, 17, 99])
def test_same_seed_reproducible(seed):
    one = build_evaluation_set(records(), 8, seed)
    two = build_evaluation_set(records(), 8, seed)
    assert [r["instruction"] for r in one.heldout] == [r["instruction"] for r in two.heldout]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("  HashMap 原理？ ", "hashmap原理"),
        ("ＡＢＣ_test", "abctest"),
        ("VOLATILE  关键字", "volatile关键字"),
        ("a-b_c", "abc"),
        ("空 格", "空格"),
    ],
)
def test_normalize_instruction(text, expected):
    assert normalize_instruction(text) == expected


@pytest.mark.parametrize(
    "record,topic",
    [
        ({"instruction": "HashMap", "output": ""}, "集合"),
        ({"instruction": "volatile", "output": ""}, "并发"),
        ({"instruction": "JVM GC", "output": ""}, "JVM"),
        ({"instruction": "Spring IoC", "output": ""}, "Spring"),
        ({"instruction": "MySQL 索引", "output": ""}, "数据与网络"),
        ({"instruction": "Java 异常", "output": ""}, "Java 基础"),
    ],
)
def test_topic_inference(record, topic):
    assert infer_topic(record) == topic


@pytest.mark.parametrize("length,expected", [(5, "短"), (18, "短"), (19, "中"), (30, "中"), (31, "长")])
def test_length_strata(length, expected):
    assert length_stratum({"instruction": "x" * length}) == expected


def test_deduplicate_normalized_instruction():
    data = records(3) + [{"instruction": " 请解释 HashMap 原理 0!!!", "output": "重复"}]
    unique, duplicates = deduplicate_records(data)
    assert len(unique) == 3
    assert len(duplicates) == 1


def test_external_training_records_are_excluded():
    data = records(20)
    split = build_evaluation_set(data, 5, seed=0, training_records=data[:10])
    train_keys = {normalize_instruction(r["instruction"]) for r in data[:10]}
    assert all(normalize_instruction(r["instruction"]) not in train_keys for r in split.heldout)


def test_leakage_report_detects_overlap():
    report = leakage_report(records(2), [records(2)[0]])
    assert report["overlap_count"] == 1
    assert not report["leakage_free"]


def test_impossible_size_rejected():
    with pytest.raises(ValueError):
        build_evaluation_set(records(3), 4)
