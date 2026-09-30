#!/usr/bin/env python3
"""生成样本销售数据 —— python-practice/02-excel-automation

任务卡：python-practice/02-excel-automation/README.md

为什么要先「造数据」：
真实报表自动化的第一步从来不是写统计逻辑，而是拿到（或伪造）一份**结构稳定、
可复现**的数据。这里的随机数固定了种子（seed=42），所以任何人任何时间跑，
得到的 CSV 都一模一样 —— 这样文档里的每个数字都能被复核。

刻意埋了三处「脏数据」，让后面的清洗步骤不是摆设：
1. 日期列混用了 `2026-01-05` 和 `2026/01/05` 两种格式
2. 有 8 行数量（qty）是空的
3. 有 5 行是完全重复的记录

运行：
    python3 make_sample_data.py     # 生成 data/*.csv
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

SEED = 42  # ← 固定种子，保证输出可复现

# 三家门店 → 每家一段「旺季系数」，让统计出来的曲线不是平的（否则图表没信息量）
STORES: dict[str, float] = {
    "北京朝阳店": 1.15,
    "上海浦东店": 1.30,
    "深圳南山店": 0.95,
}

# 品类 → 该品类下的 SKU 列表（单价区间）
CATALOG: dict[str, list[tuple[str, int, int]]] = {
    "办公用品": [
        ("A4 复印纸 500张", 22, 30),
        ("中性笔 12支装", 12, 20),
        ("文件夹 A4", 6, 12),
    ],
    "数码配件": [
        ("无线鼠标", 69, 129),
        ("Type-C 数据线 1m", 19, 39),
        ("65W 氮化镓充电器", 129, 199),
    ],
    "家居日用": [
        ("抽纸 24包", 39, 59),
        ("收纳箱 60L", 45, 79),
        ("香薰蜡烛", 59, 99),
    ],
}

START = date(2026, 1, 1)
DAYS = 181  # 2026 上半年（1/1 ~ 6/30）
FIELDS = ["date", "store", "category", "sku", "qty", "unit_price"]


def fmt_date(d: date, messy: bool) -> str:
    """messy=True 时用 `2026/01/05` 这种斜杠格式 —— 真实系统里导出的数据经常这样。"""
    return d.strftime("%Y/%m/%d") if messy else d.isoformat()


def build_rows(rng: random.Random) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for store, factor in STORES.items():
        for day_offset in range(DAYS):
            d = START + timedelta(days=day_offset)
            # 周末生意好一点；再叠一个「随月份增长」的趋势，让月度曲线有意义
            weekday_boost = 1.5 if d.weekday() >= 5 else 1.0
            month_boost = 1.0 + (d.month - 1) * 0.08
            n_txn = max(1, round(rng.gauss(2.4 * factor * weekday_boost, 0.9)))
            for _ in range(n_txn):
                category = rng.choice(list(CATALOG))
                sku, lo, hi = rng.choice(CATALOG[category])
                qty = max(1, int(rng.gauss(3 * month_boost, 1.5)))
                price = float(rng.randint(lo, hi))
                rows.append(
                    {
                        "date": fmt_date(d, messy=rng.random() < 0.25),
                        "store": store,
                        "category": category,
                        "sku": sku,
                        "qty": qty,
                        "unit_price": price,
                    }
                )
    return rows


def inject_dirt(rows: list[dict[str, object]], rng: random.Random) -> None:
    """原地注入三类脏数据。每一步都打印出来，方便对照清洗结果。"""
    # 坑 1 已由 fmt_date 随机产生，这里只统计
    messy_dates = sum(1 for r in rows if "/" in str(r["date"]))

    # 坑 2：8 行数量为空
    for r in rng.sample(rows, 8):
        r["qty"] = ""

    # 坑 3：5 行完全重复（复制某几行追加到末尾）
    for r in rng.sample(rows, 5):
        rows.append(dict(r))

    print(f"  日期格式混用（含 `/`）：{messy_dates} 行")
    print("  数量为空：8 行")
    print("  注入重复：5 行（源数据本身还会产生少量天然重复，见 report.py 的去重统计）")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    rows = build_rows(rng)
    print(f"生成 {len(rows)} 行原始记录（含脏数据前的正常部分）")
    inject_dirt(rows, rng)

    # 按门店拆成三个 CSV —— 模拟「三家店各自导出自己的表」这一真实场景，
    # 这样后面 pandas 的「合并多表」才有素材。
    by_store: dict[str, list[dict[str, object]]] = {s: [] for s in STORES}
    rng.shuffle(rows)
    for i, r in enumerate(rows):
        by_store[list(STORES)[i % len(STORES)]].append(r)

    for store, store_rows in by_store.items():
        path = DATA_DIR / f"sales-{STORE_SLUG[store]}.csv"
        # utf-8-sig：带 BOM 的 UTF-8，Excel / WPS 直接双击打开不会乱码。
        # 这是「给中国同事发 CSV」的必备细节。
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(store_rows)
        print(f"  写出 {path.relative_to(ROOT.parent.parent)}  （{len(store_rows)} 行）")

    print(f"\n合计 {sum(len(v) for v in by_store.values())} 行 → data/ 下 3 个 CSV")
    return 0


STORE_SLUG = {
    "北京朝阳店": "beijing",
    "上海浦东店": "shanghai",
    "深圳南山店": "shenzhen",
}


if __name__ == "__main__":
    raise SystemExit(main())
