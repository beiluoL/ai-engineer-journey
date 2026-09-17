"""Project 01 — Python AI CLI Assistant v0.1。

当前版本：v0.1 单轮输入输出
依赖课程：Lesson 01 — 变量 / 类型 / input / print / f-string

运行：
    python src/main.py
"""

# v0.1：最小骨架
# 用户输入 → Python 接收 → Python 输出
# 后续版本会在此基础上逐步升级

name = input("你的名字：")
goal = input("你想学的方向：")

print("\n========== AI Engineer Journey ==========")
print(f"学员：{name}")
print(f"方向：{goal}")
print("目标：AI Engineer")
print("=========================================")
