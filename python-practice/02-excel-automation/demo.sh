#!/usr/bin/env bash
# 02-excel-automation 可复现演示。
#
#   bash demo.sh > assets/run.txt
#   python3 ../../scripts/render_terminal.py <(sed -n '1,12p'  assets/run.txt) \
#       --out assets/term-02-data.png   --title "bash — 02-excel-automation/demo.sh"
#   python3 ../../scripts/render_terminal.py <(sed -n '13,$p'   assets/run.txt) \
#       --out assets/term-02-report.png --title "bash — 02-excel-automation/demo.sh"
#
# 前置：需要 pandas / openpyxl（见 ../requirements.txt）
set -u
cd "$(dirname "$0")"

PY="${PY:-python3}"

run() {
    printf '$ %s\n' "$*"
    "$@" 2>&1 || true
    printf '\n'
}

echo "# 02 Excel 报表自动化 —— 三个门店的 CSV 进，一份多 sheet 报表出"
echo

run "$PY" make_sample_data.py

echo "# 下面是报表流水线：合并 → 清洗 → 统计 → 写 Excel → 画图"
echo

run "$PY" report.py
