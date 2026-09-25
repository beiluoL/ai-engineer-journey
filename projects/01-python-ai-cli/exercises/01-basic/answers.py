"""Exercises 01-basic 参考答案（对应 Milestone 01 / 02）。

用法:
    python3 answers.py               # 全部跑一遍（用内置示例数据，不需要输入）
    python3 answers.py --interactive # 交互模式，A1/A2 真的等你键盘输入

规矩: 先自己把题敲一遍、跑通了再来看这个文件。对照差异才有学习效果。
答不出来时只看对应那一个函数，不要整份抄。
"""

import json
import os
import sys
import tempfile

# Java 类比：
#   Python 的 dict  ≈ Java 的 Map<String, Object>
#   Python 的 list  ≈ Java 的 List<Object>
#   json.dumps/load ≈ Jackson 的 writeValueAsString / readValue


# ---------- A. 变量与类型（Milestone 01） ----------

def a1(name: str, direction: str) -> str:
    """A1: f-string 自我介绍。Java 里是 String.format / 字符串拼接，这里用 f-string。"""
    intro = f"我叫 {name}，正在学 {direction}。"
    print(intro)
    return intro


def a2(raw_a: str, raw_b: str) -> dict:
    """A2: 输入两个数字，打印和差积商。

    关键点：input() 返回的永远是 str，必须自己转 float / int。
    Java 里 Scanner.nextDouble() 已经帮你转好了，Python 不会替你转。
    """
    a = float(raw_a)
    b = float(raw_b)
    result = {
        "和": a + b,
        "差": a - b,
        "积": a * b,
        # 商要防除零：Python 会抛 ZeroDivisionError，不像 Java 整数除法抛 ArithmeticException 前还得先判断
        "商": a / b if b != 0 else None,
    }
    for k, v in result.items():
        print(f"{k}: {v}")
    return result


def a3() -> None:
    """A3: 用 type() 验证类型，再把字符串转成 float 做加法。"""
    values = ["3.14", 3.14, 3, True]
    for v in values:
        print(f"{v!r} -> {type(v).__name__}")

    # str -> float，然后相加
    print(float("3.14") + 3.14)  # 6.28

    # 注意：True 的 type 是 bool，但 bool 是 int 的子类，True + 1 == 2
    print(f"True + 1 = {True + 1}")


# ---------- B. List / Dict / JSON（Milestone 02） ----------

def b1() -> list:
    """B1: 装 3 条 AI 对话消息，打印总数。"""
    messages = [
        {"role": "system", "content": "你是一个 Python 助教"},
        {"role": "user", "content": "list 和 dict 有什么区别？"},
        {"role": "assistant", "content": "list 有序下标访问，dict 键值对访问"},
    ]
    print(f"消息总数: {len(messages)}")
    return messages


def b2(messages: list) -> int:
    """B2: 追加一条 user 消息，再统计 role == 'user' 的条数。

    两种写法：普通循环（好读）/ 生成器 + sum（Pythonic）。
    """
    messages.append({"role": "user", "content": "那 JSON 呢？"})

    count = 0
    for m in messages:
        if m["role"] == "user":
            count += 1
    print(f"user 消息数（循环）: {count}")

    # 等价的 Pythonic 写法：sum(生成器)
    count2 = sum(1 for m in messages if m["role"] == "user")
    print(f"user 消息数（生成器）: {count2}")
    return count


def b3(messages: list, path: str) -> list:
    """B3: json.dumps 写文件，json.load 读回来，验证一致。

    ensure_ascii=False 让中文正常落盘（默认是 \\uXXXX 转义）；
    Java 里 Jackson 默认就是输出 UTF-8，Python 需要显式关掉转义。
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    with open(path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    print(f"读回 {len(loaded)} 条，与原数据一致: {loaded == messages}")
    return loaded


def b4() -> str:
    """B4: 追加一个 skill，缩进 2 格打印完整 JSON。"""
    data = {"name": "Beiluo", "skills": ["Java", "Python"]}
    data["skills"].append("LLM")
    text = json.dumps(data, ensure_ascii=False, indent=2)
    print(text)
    return text


def b5(path: str):
    """B5（挑战）: 安全读 JSON —— 处理「文件不存在」和「JSON 格式错误」。

    提前偷看 Milestone 06：try / except 多个异常类型，
    Python 的 try-except ≈ Java 的 try-catch，一个 try 可以挂多个 except。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[提示] 文件不存在: {path}")
    except json.JSONDecodeError as e:
        # e 自带行号列号，排查格式错误很好用
        print(f"[提示] JSON 格式错误（第 {e.lineno} 行第 {e.colno} 列）: {e.msg}")
    return None


def main() -> None:
    interactive = "--interactive" in sys.argv

    print("== A1 ==")
    if interactive:
        a1(input("你的名字: "), input("学习方向: "))
    else:
        a1("Beiluo", "Python / AI")

    print("\n== A2 ==")
    if interactive:
        a2(input("数字 a: "), input("数字 b: "))
    else:
        a2("12", "4")

    print("\n== A3 ==")
    a3()

    print("\n== B1 ==")
    msgs = b1()

    print("\n== B2 ==")
    b2(msgs)

    print("\n== B3 ==")
    tmp = os.path.join(tempfile.gettempdir(), "ex01-messages.json")
    b3(msgs, tmp)

    print("\n== B4 ==")
    b4()

    print("\n== B5 ==")
    b5(tmp)                                   # 正常情况
    b5(os.path.join(tempfile.gettempdir(), "no-such-file.json"))  # 文件不存在
    bad = os.path.join(tempfile.gettempdir(), "ex01-bad.json")
    with open(bad, "w", encoding="utf-8") as f:
        f.write("{not valid json")            # 故意写坏
    b5(bad)                                   # 格式错误


if __name__ == "__main__":
    main()
