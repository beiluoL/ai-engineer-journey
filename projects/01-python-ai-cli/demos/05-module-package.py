"""第 05 章 demo：模块与包

运行方式（在 projects/01-python-ai-cli 目录下执行）：
    python3 demos/05-module-package.py

本文件会真的去 import 同目录下的 pkgdemo 包：
    demos/pkgdemo/__init__.py
    demos/pkgdemo/llm.py
    demos/pkgdemo/utils.py
    demos/pkgdemo/cli/__init__.py
    demos/pkgdemo/cli/main.py

里面不联网、不需要 API Key。
"""

import os
import sys

# ---------------------------------------------------------------
# 0. 先看一眼 sys.path：Python 到底去哪些地方找模块
# ---------------------------------------------------------------
print("===== 0. sys.path 是什么 =====")
print("当前解释器：", sys.executable)
print("当前工作目录：", os.getcwd())
print("sys.path 里的前 5 个查找位置：")
for i, item in enumerate(sys.path[:5], start=1):
    print(f"   {i}. {item}")
print()
print(">>> 注意第 1 条：它就是 demos 这个目录。")
print(">>> 因为 python3 在跑 demos/05-module-package.py 时，")
print(">>> 会自动把「脚本所在的目录」放到 sys.path 最前面。")
print(">>> 所以 pkgdemo 就在 demos/ 里面，这里才能直接 import。")

# ---------------------------------------------------------------
# 1. import 到底在做什么：先执行一次 import
# ---------------------------------------------------------------
print()
print("===== 1. 第一次 import pkgdemo =====")
import pkgdemo  # noqa: E402

print("import 完了，pkgdemo.__version__ =", pkgdemo.__version__)
print("pkgdemo.__file__ =", pkgdemo.__file__)
print(">>> 注意上面 __init__.py 里的 print 在 import 时就自动执行了。")

# ---------------------------------------------------------------
# 2. 同一个模块 import 两次，会不会执行两遍 __init__？
# ---------------------------------------------------------------
print()
print("===== 2. 再 import 一次 pkgdemo =====")
import pkgdemo as pkgdemo_again  # noqa: E402

print("还是同一个对象吗？", pkgdemo_again is pkgdemo)
print(">>> 是同一份，Python 有缓存（sys.modules），不会重复执行。")

import sys as sys_module  # noqa: E402

print("sys.modules 里的键，只看和 pkgdemo 有关的：")
for key in list(sys_module.modules.keys()):
    if key.startswith("pkgdemo"):
        print(f"   {key}")

# ---------------------------------------------------------------
# 3. 两种导入方式：import 与 from ... import ...
# ---------------------------------------------------------------
print()
print("===== 3. import 与 from ... import ... =====")

from pkgdemo.llm import chat, count_messages  # noqa: E402

print("from 之后可以直接用：", chat.__name__, "/", count_messages.__name__)
print("chat 来自哪个文件：", chat.__module__)

import pkgdemo.llm as llm  # noqa: E402

print("用 import 方式：", llm.chat.__name__)
print(">>> 两种方式都能拿到同一个函数，只是写法不同。")

# ---------------------------------------------------------------
# 4. 真的调用一次「模块化的」AI CLI
# ---------------------------------------------------------------
print()
print("===== 4. 调用 pkgdemo 里的模块 =====")

messages = [
    {"role": "system", "content": "你是一个 Python 老师"},
    {"role": "user", "content": "什么是列表推导式？"},
]
print("提问前 messages：")
for m in messages:
    print(f"   [{m['role']}] {m['content']}")

reply = chat(messages, model="mock-llm")
messages.append(reply)

print("得到回复：", reply["content"])
print("回复里的模型名：", reply["model"])
print("现在 messages 的统计：", count_messages(messages))

# ---------------------------------------------------------------
# 5. 两层包：pkgdemo.cli.main
# ---------------------------------------------------------------
print()
print("===== 5. 两层包 =====")
print("目录结构是这样的：")
print("   demos/pkgdemo/__init__.py      <- 一层包")
print("   demos/pkgdemo/llm.py           <- 一层包里的模块")
print("   demos/pkgdemo/utils.py")
print("   demos/pkgdemo/cli/__init__.py  <- 二层包")
print("   demos/pkgdemo/cli/main.py      <- 二层包里的模块")

import pkgdemo.cli.main as cli_main  # noqa: E402

print("导入 pkgdemo.cli.main 成功了。")
print("cli_main.__name__ =", cli_main.__name__)
print("cli_main.run 是不是一个函数：", callable(cli_main.run))
print(">>> 注意上面 pkgdemo/cli/__init__.py 的 print 也执行了。")
print(">>> 但是 cli_main.run() 没有被调用，因为 main.py 里")
print(">>> `if __name__ == \"__main__\"` 为假，跳过了。")

# ---------------------------------------------------------------
# 6. __name__ 的两种结局
# ---------------------------------------------------------------
print()
print("===== 6. __name__ 是什么 =====")
print("当前这个 demo 文件的 __name__ =", __name__)
print("当直接运行 python3 一个 .py 文件时，它的 __name__ 是 '__main__'；")
print("但当被 import 时，它的 __name__ 就是模块名。")

import runpy  # noqa: E402

_demo_dir = os.path.dirname(os.path.abspath(__file__))
namespace = runpy.run_path(
    os.path.join(_demo_dir, "pkgdemo", "cli", "main.py"),
    run_name="__main__",
)
print()
print(">>> 现在用 run_name=\"__main__\" 把 main.py 当成脚本跑一遍：")
print(">>> （上面那段输出就是 main.py 自己打印出来的）")
print(">>> runpy.run_path 的返回值里存着 main.py 执行完的全局变量")
print("main.py 里的 __name__ =", namespace["__name__"])
print(">>> 只有它是 '__main__' 的时候，runpy 才会让 main.py 里的")
print(">>> `if __name__ == \"__main__\"` 成立、把 run() 执行起来。")

# ---------------------------------------------------------------
# 7. 用包的方式重新跑一遍
# ---------------------------------------------------------------
print()
print("===== 7. 以 -m 模块方式运行 main.py =====")
import subprocess  # noqa: E402

result = subprocess.run(
    [sys.executable, "-m", "pkgdemo.cli.main"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
    capture_output=True,
    text=True,
)
print("退出码：", result.returncode)
print("输出内容：")
for line in result.stdout.rstrip().splitlines():
    print("   " + line)

print()
print("================ 小结 ================")
print("1. 模块就是一个 .py 文件，import 时会把文件跑一遍。")
print("2. from x import y 和 import x.y 都能用，看场景。")
print("3. 包 = 带 __init__.py 的目录，点号的层级就是目录层级。")
print("4. __name__ == \"__main__\" 用来区分「被导入」和「被直接运行」。")
print("5. sys.path 是 Python 找模块的搜索路径清单。")
