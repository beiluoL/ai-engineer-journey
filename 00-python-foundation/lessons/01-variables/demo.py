"""Lesson 01 — Python 变量、类型与输入输出 Demo。

运行：
    cd 00-python-foundation/lessons/01-variables
    python demo.py
"""

# === 1. 变量与基础类型 ===
name = "Beiluo"
age = 29
score = 95.5
learning_ai = True
nothing = None

# === 2. type() 查看类型 ===
print("--- 基础类型 ---")
print(f"name          = {name!r}   type = {type(name).__name__}")
print(f"age           = {age}        type = {type(age).__name__}")
print(f"score         = {score}      type = {type(score).__name__}")
print(f"learning_ai   = {learning_ai}    type = {type(learning_ai).__name__}")
print(f"nothing       = {nothing}    type = {type(nothing).__name__}")

# === 3. f-string ===
print("\n--- f-string ---")
language = "Python"
days = 1
print(f"我已经学习 {language} {days} 天")

# === 4. input() + 类型转换 ===
print("\n--- 学习档案 ---")
your_name = input("你的名字：")
your_age = int(input("你的年龄："))
your_role = input("你的职业：")

print("\n========== 学习档案 ==========")
print(f"姓名：{your_name}")
print(f"年龄：{your_age}")
print(f"职业：{your_role}")
print("目标：AI Engineer")
print("==============================")
