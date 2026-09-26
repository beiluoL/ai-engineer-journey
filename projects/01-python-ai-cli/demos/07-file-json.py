"""第 07 章 demo：文件与 JSON

运行方式（在 projects/01-python-ai-cli 目录下执行）：
    python3 demos/07-file-json.py

本 demo 会真的在 demos/tmp-demo07/ 下建临时文件，
跑完之后自动删除，不会污染仓库。

演示内容：
    1. pathlib.Path 和 os.path 的对比
    2. "w" 模式：新建 / 覆盖（这就是它的坑）
    3. "a" 模式：追加
    4. "r" 模式：读取
    5. with open(...) 与手动 close 的区别
    6. json.dump() 把 messages 存成文件
    7. json.load() 读回来并校验
    8. 文件损坏时的处理

里面不联网、不需要 API Key。
"""

import json
import os
import shutil
from pathlib import Path

# demos/tmp-demo07/ 是给本 demo 用的临时目录
BASE = Path(__file__).resolve().parent / "tmp-demo07"
NOTES = BASE / "notes.txt"
HISTORY = BASE / "history.json"

# ---------------------------------------------------------------
# 0. 先认识 pathlib.Path
# ---------------------------------------------------------------
print("===== 0. pathlib.Path 是什么 =====")

BASE.mkdir(parents=True, exist_ok=True)
print("临时目录已建好：", BASE)
print("  它是 Path 对象吗：", isinstance(BASE, Path))
print("  .name   =", BASE.name)
print("  .suffix =", NOTES.suffix)
print("  拼路径：BASE / 'notes.txt' =", BASE / "notes.txt")
print("  用 os.path 拼出来    =", os.path.join(str(BASE), "notes.txt"))
print()
print(">>> 用 Path 之后，不再需要 os.path.join、os.path.exists 这一串函数，")
print(">>> 直接 Path('a') / 'b' 和 path.exists() 就行。")

print()
print("文件现在存在吗：", HISTORY.exists())

# ---------------------------------------------------------------
# 1. "w" 模式：没有就新建，有就清空重写
# ---------------------------------------------------------------
print()
print("===== 1. \"w\" 模式：新建或清空 =====")

with open(NOTES, "w", encoding="utf-8") as f:
    f.write("第一条笔记：Python 里 open() 默认就是 'r' 模式。\n")
print("第一次用 w 写完，读回来是：")
print("   ", NOTES.read_text(encoding="utf-8").strip())

print()
print(">>> 现在再用 w 打开一次，写点别的东西：")
with open(NOTES, "w", encoding="utf-8") as f:
    f.write("第二条笔记：'w' 会先把原来的内容清空。\n")
print("读回来发现第一条已经不见了：")
print("   ", NOTES.read_text(encoding="utf-8").strip())
print(">>> 这就是 'w' 的坑：删掉原文之前没有任何提示。")

# ---------------------------------------------------------------
# 2. "a" 模式：追加
# ---------------------------------------------------------------
print()
print("===== 2. \"a\" 模式：追加 =====")

with open(NOTES, "a", encoding="utf-8") as f:
    f.write("第三条笔记：'a' 是 append，写在文件的最后。\n")
    f.write("第四条笔记：历史记录一定要用 'a' 保存。\n")

print("追加完再读一遍：")
print("   ", NOTES.read_text(encoding="utf-8").strip())

# ---------------------------------------------------------------
# 3. 三种模式速查 + with 与不用 with 的区别
# ---------------------------------------------------------------
print()
print("===== 3. with open(...) =====")

no_with = BASE / "no-with.txt"
f = open(no_with, "w", encoding="utf-8")
f.write("不用 with 写的一句话")
print("写完了，但还没 close，此时 f.closed =", f.closed)
f.close()
print("手动 close 之后，f.closed =", f.closed)
print(">>> 忘了 close 会怎样？文件句柄占着不放，")
print(">>> Windows 上甚至没法删，而且内容可能还没真正落盘。")

with_p = BASE / "with.txt"
with open(with_p, "w", encoding="utf-8") as f2:
    f2.write("用 with 写的一句话")
    print("  在 with 里面，f2.closed =", f2.closed)
print("  出了 with，f2.closed =", f2.closed)
print(">>> with 会在代码块结束时自动 close，不用担心忘记。")

print()
print("三种模式速查：")
print("   'r' read   = 读，文件必须存在")
print("   'w' write  = 写，不存在就新建，存在就清空")
print("   'a' append = 追加，不存在就新建，存在就写到末尾")
print("   还有 'r+'(读写) / 'w+'(新建读写) / 'rb'(二进制读) 等等")

# ---------------------------------------------------------------
# 4. 读文件：read / readline / readlines
# ---------------------------------------------------------------
print()
print("===== 4. 读文件 =====")
print("整个文件一次性读完（read()）：")
print(NOTES.read_text(encoding="utf-8"))

with open(NOTES, "r", encoding="utf-8") as f3:
    lines = f3.readlines()
print("readlines() 拿到一个列表：", lines)
print("列表长度：", len(lines))
print("逐行打印：")
for i, line in enumerate(lines, start=1):
    print(f"   第 {i} 行：{line.rstrip(chr(10))}")

# ---------------------------------------------------------------
# 5. json.dump()：把 messages 存成文件
# ---------------------------------------------------------------
print()
print("===== 5. json.dump() 保存 messages =====")

messages = [
    {"role": "system", "content": "你是一个耐心的 Python 老师"},
    {"role": "user", "content": "什么是 f-string？"},
    {"role": "assistant", "content": "f-string 就是在字符串前面加 f，用 {} 里放变量。"},
    {"role": "user", "content": "那它和 .format() 有啥区别？"},
]

print("内存里的 messages 有", len(messages), "条：")
for m in messages:
    print(f"   [{m['role']}] {m['content']}")

print()
print(">>> 注意：messages 里是中文，dump 的时候一定要写 ensure_ascii=False，")
print(">>> 否则中文会变成 \\uXXXX 这种看不懂的转义。")

with open(HISTORY, "w", encoding="utf-8") as f4:
    json.dump(messages, f4, ensure_ascii=False, indent=2)

print("内存里的对象 -> 文件里的内容（下面是文件原文）：")
print("=" * 20)
print(HISTORY.read_text(encoding="utf-8"))
print("=" * 20)

print("文件大小（字节）：", HISTORY.stat().st_size)

# ---------------------------------------------------------------
# 6. json.load()：读回来并校验
# ---------------------------------------------------------------
print()
print("===== 6. json.load() 读回来 =====")

with open(HISTORY, "r", encoding="utf-8") as f5:
    loaded = json.load(f5)

print("读回来的类型：", type(loaded).__name__)
print("和内存里那一堆是相等的吗：", loaded == messages)
print("条数：", len(loaded))
print()
print("逐条校验：")
for i, m in enumerate(loaded, start=1):
    print(f"   {i}. role = {m['role']:<9} 合法吗：{m['role'] in ('system', 'user', 'assistant')}")

print()
print(">>> dumps/load 处理「字符串 -> 字符串」，dump/load 处理「文件」。")
print(">>> 名字对照：dumps = dump string，loads = load string。")
print(">>> 读回来之后，它就是普通的 list of dict，操作方式和内存里一模一样。")

# ---------------------------------------------------------------
# 7. 文件不存在 / 文件损坏
# ---------------------------------------------------------------
print()
print("===== 7. 读的时候可能出问题 =====")

missing = BASE / "not-exist.json"
try:
    with open(missing, "r", encoding="utf-8") as f6:
        json.load(f6)
except FileNotFoundError as e:
    print("文件不存在 -> FileNotFoundError：", e)
    print(">>> 第一次启动、或者用户换过电脑，就是这种情况。")

broken = BASE / "broken.json"
broken.write_text('[{"role": "user", "content": "你好",}]', encoding="utf-8")
print()
print("故意写坏一个文件：", broken.read_text(encoding="utf-8"))
try:
    with open(broken, "r", encoding="utf-8") as f7:
        json.load(f7)
except json.JSONDecodeError as e:
    print("内容不是合法 JSON -> JSONDecodeError：", e)
    print("   出错第", e.lineno, "行，第", e.colno, "列：", e.msg)

# ---------------------------------------------------------------
# 8. 收尾：把临时文件删掉
# ---------------------------------------------------------------
print()
print("===== 8. 清理临时文件 =====")
print("删除前，目录里有：", sorted(p.name for p in BASE.iterdir()))
shutil.rmtree(BASE)
print("已经删除整个临时目录：", BASE, "还存在吗：", BASE.exists())

# ---------------------------------------------------------------
# 小结
# ---------------------------------------------------------------
print()
print("================ 小结 ================")
print("1. 用 pathlib.Path，路径拼装不用再纠结斜杠。")
print("2. 'r' 读 / 'w' 覆盖写 / 'a' 追加，读写都要写 encoding='utf-8'。")
print("3. 一律用 with open(...) as f，它会帮你 close。")
print("4. json.dump 写文件、json.load 读文件；dumps/loads 只处理字符串。")
print("5. 存中文加 ensure_ascii=False，调 indent=2 方便人肉查看。")
print("6. 历史记录文件第一次读会 FileNotFoundError，属于正常情况。")
