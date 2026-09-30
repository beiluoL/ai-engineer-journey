#!/usr/bin/env bash
# 01-todo-cli 可复现演示：真实执行下面每一条命令，并原样打印。
#
#   bash demo.sh > assets/run.txt
#   python3 ../../scripts/render_terminal.py assets/run.txt \
#       --out assets/term-01-todo-cli.png --title "bash — 01-todo-cli/demo.sh"
#
# 为什么用脚本而不是手截图：终端截图带用户名、路径、历史命令，还得手动裁；
# 这里每次跑出来的输出完全一致，可以进 Git、可以被 CI 校验。
set -u
cd "$(dirname "$0")"

PY="${PY:-python3}"
rm -f todos.json          # 从零开始，保证输出每次一致

run() {                   # 先打印命令（render_terminal 会把 `$ ` 行渲染成绿色提示符）
    printf '$ %s\n' "$*"
    "$@" 2>&1 || true
    printf '\n'
}

echo "# 01 命令行待办清单 —— 从零跑一遍（增删改查 + 落盘）"
echo

run "$PY" todo.py list

run "$PY" todo.py add "读完 Python 官方教程第 4 章（函数）"
run "$PY" todo.py add "给 todo.py 补上单元测试"
run "$PY" todo.py add "把这段代码用 type hints 重写"

run "$PY" todo.py list

run "$PY" todo.py done 1
run "$PY" todo.py list

run "$PY" todo.py rm 3
run "$PY" todo.py list

echo "# 数据长这样：todos.json 是纯文本，随时能 cat / 手改 / 进 Git"
echo '$ cat todos.json'
cat todos.json
echo

echo "# 出错时不该甩 traceback，而是一句人话 —— 这就是产品感"
run "$PY" todo.py done 99

rm -f todos.json
