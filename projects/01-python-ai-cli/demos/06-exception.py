"""第 06 章 demo：异常

运行方式（在 projects/01-python-ai-cli 目录下执行）：
    python3 demos/06-exception.py

演示内容：
    1. 不处理异常会发生什么（真的崩给你看，红字 Traceback）
    2. try + except 接住它
    3. 三种具体异常：ZeroDivisionError / FileNotFoundError / json.JSONDecodeError
    4. except 后面可以拿到异常对象
    5. else / finally 的执行顺序
    6. raise 主动抛出自己的异常

里面不联网、不需要 API Key。
"""

import json
import subprocess
import sys

# ---------------------------------------------------------------
# 1. 先看看「什么都不做」的后果
# ---------------------------------------------------------------
print("===== 1. 不处理异常会怎样 =====")
print("下面这段程序是对的写法，但没有 try，我们让它真的崩一次：")
print()
print("    def divide(a, b):")
print("        return a / b")
print()
print("    print(divide(1, 0))")
print()

crash_code = (
    "def divide(a, b):\n"
    "    return a / b\n"
    "\n"
    "print('结果：', divide(1, 0))\n"
)
result = subprocess.run(
    [sys.executable, "-c", crash_code], capture_output=True, text=True
)

print("命令的退出码（非 0 就是崩了）：", result.returncode)
print("程序自己打印到 stdout 的内容：", repr(result.stdout))
print("Python 打印到 stderr 的内容，原文如下：")
print(result.stderr, end="")
print()
print(">>> 看到了吗：程序没有给出任何提示就「炸」了，")
print(">>> 用户只看到一段天书一样的报错信息，完全不知道该干啥。")

# ---------------------------------------------------------------
# 2. try + except：接住它
# ---------------------------------------------------------------
print()
print("===== 2. try + except =====")


def divide(a, b):
    return a / b


try:
    print("结果：", divide(1, 0))
except ZeroDivisionError:
    print("出错了：除数不能是 0，请重新输入一个非零数字")
print("程序继续往下跑了，没有崩。")

# ---------------------------------------------------------------
# 3. 三种具体的异常，分别接住
# ---------------------------------------------------------------
print()
print("===== 3. 三种具体的异常 =====")

print("--- 3.1 除以 0 ---")
try:
    score = 100
    print(score / 0)
except ZeroDivisionError as e:
    print("捕获 ZeroDivisionError：", e)

print()
print("--- 3.2 打开一个不存在的文件 ---")
try:
    with open("demos/06-not-exist.txt", "r", encoding="utf-8") as f:
        print(f.read())
except FileNotFoundError as e:
    print("捕获 FileNotFoundError：", e)
    print(">>> 第一次启动时历史文件还不存在，就是这种情况。")

print()
print("--- 3.3 解析一段写坏的 JSON ---")
broken_json = '{"role": "user", "content": "你好",}'
print("坏掉的 JSON 内容：", broken_json)
try:
    data = json.loads(broken_json)
    print("解析成功：", data)
except json.JSONDecodeError as e:
    print("捕获 json.JSONDecodeError：", e)
    print("异常对象里的三个信息：lineno =", e.lineno, "/ colno =", e.colno, "/ msg =", e.msg)

print()
print("--- 3.4 把一个不是数字的字符串转成 int ---")
try:
    print(int("我不是一个数字"))
except ValueError as e:
    print("捕获 ValueError：", e)

# ---------------------------------------------------------------
# 4. except 后面拿到异常对象
# ---------------------------------------------------------------
print()
print("===== 4. 异常对象里有什么 =====")

numbers = ["10", "3.5", "abc"]
for raw in numbers:
    try:
        value = int(raw)
    except ValueError as e:
        print(f"   {raw!r} -> 转不了，异常类型 {type(e).__name__}，信息：{e}")
    else:
        print(f"   {raw!r} -> 转成 {value!r}，类型是 {type(value).__name__}")

# ---------------------------------------------------------------
# 5. else 与 finally 的执行顺序
# ---------------------------------------------------------------
print()
print("===== 5. else / finally 的执行顺序 =====")


def process(should_fail):
    print("  [函数] 开始处理")
    try:
        print("  [try] 真正干活")
        if should_fail:
            raise ValueError("模拟：这一步出了问题")
    except ValueError as e:
        print("  [except] 捕获到异常：", e)
    else:
        print("  [else] 没有异常，做额外收尾（比如写日志）")
    finally:
        print("  [finally] 无论有没有异常，这里都会执行")
    print("  [函数] 处理结束")


print("--- 情况 A：一切正常 ---")
process(False)
print("--- 情况 B：中途出错 ---")
process(True)

print()
print("--- finally 在 return 之前也会先执行 ---")


def demo_return_vs_finally():
    try:
        return "这是 return 出去的值"
    finally:
        print("  [finally] 在 return 之前先跑完")


print("  返回值：", demo_return_vs_finally())
print(">>> 所以释放文件、关闭连接这类事情，最适合写在 finally 里。")

# ---------------------------------------------------------------
# 6. raise：主动抛出自己的异常
# ---------------------------------------------------------------
print()
print("===== 6. raise 自定义异常 =====")


class EmptyQuestionError(Exception):
    """这是我们自己定义的「业务异常」。"""


class RateLimitError(Exception):
    """这是我们自己定义的第二种业务异常。"""


def ask_bot(question, balance=10):
    """模拟一次提问，做业务校验。"""
    if not question or not question.strip():
        raise EmptyQuestionError("问题不能为空，请输入你想问的内容")
    if balance <= 0:
        raise RateLimitError("余额不足，请充值后再问")
    return {"role": "assistant", "content": f"[模拟回复] {question}"}


print("正常提问：", ask_bot("什么是列表推导式？"))
print()

print("第一次提问：空字符串")
try:
    ask_bot("")
except EmptyQuestionError as e:
    print("  被 EmptyQuestionError 接住：", e)

print("第二次提问：全是空格")
try:
    ask_bot("   ")
except EmptyQuestionError as e:
    print("  被 EmptyQuestionError 接住：", e)

print("第三次提问：余额不足")
try:
    ask_bot("余额还剩多少？", balance=0)
except RateLimitError as e:
    print("  被 RateLimitError 接住：", e)

print("第四次提问：正常")
try:
    answer = ask_bot("Python 怎么读文件？")
except (EmptyQuestionError, RateLimitError) as e:
    print("  出错了：", e)
else:
    print("  收到的回复：", answer["content"])

print()
print(">>> 技术层问题（文件不存在 / 网络断了）用 Python 自带的异常；")
print(">>> 业务层问题（问题为空 / 余额不足）用 raise 抛自己的异常；")
print(">>> 两者在 UI 层的表现可以完全不一样。")

print()
print("================ 小结 ================")
print("1. 不处理异常，程序就会崩掉并打印一段红色的报错信息。")
print("2. try 包住「可能出错」的那一小段，except 接住具体异常。")
print("3. except 拿到的 e 里有类型、信息、出错行号，够你定位问题。")
print("4. else 只在没异常时跑，finally 不管怎样都跑。")
print("5. raise 用来表达「业务规则不满足」。")
