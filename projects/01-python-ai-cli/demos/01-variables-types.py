"""Milestone 01 实验：变量、类型、input()、f-string。

配套文档: milestones/01-variables.md

两种运行方式（都可以，不需要改代码）:
    python3 demos/01-variables-types.py
    printf '29\n3.5\n' | python3 demos/01-variables-types.py

第二种是"用管道喂输入"，和第 5 节的 input() 对应。
没有检测到输入时会自动使用示例数据，方便直接双击运行。
"""

print("===== 1. 变量：给数据绑定一个名字 =====")

name = "Beiluo"
role = "Java 开发工程师"
age = 29
study_hours = 3.5
learning_ai = True

print(f"name = {name!r}")
print(f"role = {role!r}")
print(f"age = {age!r}")
print(f"study_hours = {study_hours!r}")
print(f"learning_ai = {learning_ai!r}")

print("\n===== 2. type()：Python 怎么知道数据是什么类型 =====")

for value in (name, role, age, study_hours, learning_ai):
    print(f"{value!r} 的类型是 {type(value).__name__}")

print("\n===== 3. 一行给多个变量赋值 =====")

x, y = 1, 2
print(f"x, y = {x}, {y}")

x, y = y, x                      # 不需要临时变量就能交换
print(f"交换后 x, y = {x}, {y}")

count, price, title = 3, 9.5, "Python 入门"
print(f"count={count}, price={price}, title={title!r}")

print("\n===== 4. 变量重新赋值：id() 会变吗 =====")

a = 100
print(f"现在 a = 100   -> 对象 id = {id(a)}")

a = 100                          # 同一个小整数，还是同一个对象
print(f"再赋 100       -> 对象 id = {id(a)}")

a = "hello"
print(f'改成 "hello"   -> 对象 id = {id(a)}')

print("变量名更像贴在对象上的标签：换成另一个对象，id 就变。")

print("\n===== 5. input()：拿用户输入，但永远拿到字符串 =====")


def ask(prompt, example):
    """真的用 input() 读键盘；没有输入（EOF）时回退到示例数据。"""
    try:
        return input(prompt).strip() or example
    except EOFError:
        print(f"（没有检测到输入，使用示例数据：{example}）")
        return example


raw_age = ask("请输入年龄：", "29")
print()
print(f"raw_age = {raw_age!r}  类型是 {type(raw_age).__name__}")

age = int(raw_age)
print(f"int() 之后 age = {age!r}  类型是 {type(age).__name__}")

raw_hours = ask("请输入每天学习时间：", "3.5")
print()
study_hours = float(raw_hours)
print(f"study_hours = {raw_hours!r}  类型是 {type(raw_hours).__name__}")
print(f"float() 之后 study_hours = {study_hours!r}  类型是 {type(study_hours).__name__}")

print("\n===== 6. f-string：把变量放进文本 =====")

weekly_hours = study_hours * 7

print(f"姓名：{name}")
print(f"职业：{role}")
print(f"每天学习：{study_hours} 小时")
print(f"每周学习：{weekly_hours} 小时")
print(f"每周学习（保留一位小数）：{weekly_hours:.1f} 小时")
print(f"完成度：{0.8:.0%}")
print(f"编号补零：{7:03d}")
print(f"大括号里直接算：{study_hours} * 7 = {study_hours * 7}")
print(f"名字有 {len(name)} 个字符")

print("\n===== 7. 动态类型：同一个名字可以换类型 =====")

value = 10
print(f"value = 10 的时候 -> {type(value).__name__}")

value = "hello"
print(f'value = "hello" 的时候 -> {type(value).__name__}')

print("Java 写 `String name` / `int age`；Python 只写名字，运行时才决定类型。")
