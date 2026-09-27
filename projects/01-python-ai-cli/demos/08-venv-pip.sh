#!/usr/bin/env bash
# Milestone 08 实验：venv 从创建到退出，以及 pip list 的隔离效果。
# 全部命令真实执行，不使用任何模拟输出。
set -u

WORK=/tmp/p01-venv-demo
rm -rf "$WORK" && mkdir -p "$WORK"
cd "$WORK" || exit 1

echo "===== 1. 创建之前的 python / pip 在哪 ====="
echo "which python3 -> $(which python3)"
python3 --version

echo
echo "===== 2. python3 -m venv .venv 创建独立环境 ====="
python3 -m venv .venv
echo "退出码 $?"
ls -1 .venv

echo
echo "===== 3. 产生的目录结构 ====="
ls -1 .venv/bin | head -12

echo
echo "===== 4. 激活之后：python / pip 已经指向虚拟环境 ====="
# shellcheck disable=SC1091
source .venv/bin/activate
echo "which python -> $(which python)"
echo "which pip    -> $(which pip)"
python --version
pip --version

echo
echo "===== 5. pip list：一个干净环境里只有这些 ====="
pip list

echo
echo "===== 6. 装一个包，看它被装到哪 ====="
pip install --quiet six 2>&1 | tail -3
python -c "import six, sys; print('six 路径:', six.__file__)"
echo "→ 路径在 .venv 里面，系统环境不受影响"

echo
echo "===== 7. pip freeze > requirements.txt（可复现的依赖清单）====="
pip freeze > requirements.txt
cat requirements.txt

echo
echo "===== 8. deactivate：退出后回到系统 python ====="
deactivate
echo "which python3 -> $(which python3)"
echo "VIRTUAL_ENV=${VIRTUAL_ENV:-（已清空）}"
