"""第 04 章 demo：函数

运行方式（在本目录的上一级执行，即 projects/01-python-ai-cli/）：
    python3 demos/04-function.py

演示内容：
    1. 最简单的函数 + 文档字符串
    2. 位置参数 / 默认参数 / 关键字参数
    3. 多返回值（其实是元组）
    4. *args 与 **kwargs
    5. 可变默认参数陷阱（第二次调用会被污染！）
    6. lambda + sorted(key=...)

本文件只用标准库，不联网、不需要 API Key。
"""

# ---------------------------------------------------------------
# 1. 函数的基本样子：def + 参数 + return
# ---------------------------------------------------------------
print("===== 1. 定义一个最简单的函数 =====")


def greet(name):
    """打招呼。

    三引号里面的是「文档字符串」，可以用 help(greet) 看到。
    """
    return f"你好，{name}！欢迎开始今天的 Python 学习。"


print(greet("小明"))
print(greet("Beiluo"))
print("函数本身只是一个对象：", greet)
print("类型也是函数类型：", type(greet).__name__)

# ---------------------------------------------------------------
# 2. 默认参数：调用时可以省略不传
# ---------------------------------------------------------------
print()
print("===== 2. 默认参数 =====")


def ask(question, model="gpt-4o-mini", max_tokens=500):
    """模拟一次提问。model 和 max_tokens 都有默认值。"""
    return {
        "model": model,
        "question": question,
        "max_tokens": max_tokens,
    }


# 只传必须的 question
print("只传问题：", ask("Python 里的列表和数组是一回事吗？"))
# 传一个自定义 model
print("传自定义模型：", ask("什么是 f-string？", model="deepseek-chat"))
# 用「关键字参数」传，顺序可以乱
print(
    "关键字乱序：",
    ask("怎么读一个 json 文件？", max_tokens=1024, model="qwen-turbo"),
)

print()
print("注意：默认参数必须放在普通参数的后面，不然 def 这一行直接就过不了。")

# ---------------------------------------------------------------
# 3. 多返回值：返回的是元组，可以一次性解包
# ---------------------------------------------------------------
print()
print("===== 3. 返回多个值 =====")


def split_sentence(text):
    """把一个句子拆成「中文 / 英文单词 / 数字」三份。"""
    chinese = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    words = "".join(ch for ch in text if ch.isascii() and ch.isalpha()).lower()
    digits = "".join(ch for ch in text if ch.isdigit())
    return chinese, words, digits


cn, en, num = split_sentence("学习 AI 一共用了 30 天")
print("原文：", "学习 AI 一共用了 30 天")
print("中文部分：", cn)
print("英文部分：", en)
print("数字部分：", num)
print("其实返回的是一个元组：", split_sentence("学习 AI 一共用了 30 天"))


# ---------------------------------------------------------------
# 4. *args 收集位置参数，**kwargs 收集关键字参数
# ---------------------------------------------------------------
print()
print("===== 4. *args 与 **kwargs =====")


def total_price(*prices, currency="人民币"):
    """*prices 会把多传进来的位置参数装成一个元组。"""
    if not prices:
        return 0.0
    return f"共 {len(prices)} 件，合计 {sum(prices):.2f} {currency}"


print("一个参数：", total_price(9.9))
print("三个参数：", total_price(9.9, 19.9, 5.0))
print("零个参数：", total_price())
print("换个货币：", total_price(9.9, 19.9, currency="美元"))


def chat(**kwargs):
    """**kwargs 会把关键字参数装成一个普通字典。"""
    print("收到的 kwargs 类型是：", type(kwargs).__name__)
    print("内容：", kwargs)
    return {"ok": True, " echoed ": kwargs}


chat(role="user", content="你好")
chat()


def mixed(a, b, *args, **kwargs):
    """四种参数可以一起出现，顺序是：普通 → *args → **kwargs。"""
    print(f"a={a}, b={b}")
    print(f"args={args}")
    print(f"kwargs={kwargs}")


mixed(1, 2, 3, 4, name="小红", age=18)

# ---------------------------------------------------------------
# 5. 可变默认参数陷阱（这是新手最常踩的坑之一）
# ---------------------------------------------------------------
print()
print("===== 5. 可变默认参数陷阱（重要！）=====")


# 看起来「没问题」的写法：默认参数是一个列表
def add_word_bad(word, words=[]):
    words.append(word)
    return words


print("第一次调用 add_word_bad('apple')：", add_word_bad("apple"))
print("第二次调用 add_word_bad('banana')：", add_word_bad("banana"))
print("第三次调用 add_word_bad('cherry')：", add_word_bad("cherry"))
print()
print(">>> 上面三次调用结果越来越长，而且 'apple' 也在！")
print(">>> 原因：带默认值的参数在 def 那一行就被创建、只创建一次，")
print(">>> 之后每次调用都复用同一个列表对象。")
print(">>> 所以一定要传新的空列表，而不是复用同一个。")

print()
print("正确写法 1：默认参数用 None，函数里面再新建。")


def add_word_good(word, words=None):
    if words is None:
        words = []
    words.append(word)
    return words


print("第一次：", add_word_good("apple"))
print("第二次：", add_word_good("banana"))
print("第三次：", add_word_good("cherry"))

print()
print("正确写法 2：调用时自己传一个新列表。")
print("第一次：", add_word_bad("apple", []))
print("第二次：", add_word_bad("banana", []))
print("第三次：", add_word_bad("cherry", []))

# ---------------------------------------------------------------
# 6. lambda + sorted(key=...)
# ---------------------------------------------------------------
print()
print("===== 6. lambda 与 sorted(key=...) =====")

messages = [
    {"role": "user", "content": "帮我解释一下什么是递归"},
    {"role": "assistant", "content": "递归就是函数自己调用自己。"},
    {"role": "user", "content": "那什么时候该用 while 呢？"},
    {"role": "assistant", "content": "次数未知时用 while，次数已知时用 for。"},
]

print("原始顺序（一条条看）：")
for m in messages:
    print(f"   {m['role']:<9} -> {m['content']}")

print()
print("按 content 长度从短到长排：")
for m in sorted(messages, key=lambda item: len(item["content"])):
    print(f"   {m['role']:<9} -> {len(m['content']):>2} 字 | {m['content']}")

print()
print("按 role 分组排（system < user < assistant）：")
for m in sorted(messages, key=lambda item: item["role"]):
    print(f"   {m['role']:<9} -> {m['content']}")

print()
print("lambda 就是一个「只有一行的小函数」：")
print("   len_of = lambda text: len(text)")
print("   等价于 def len_of(text): return len(text)")
len_of = lambda text: len(text)
print("   len_of('hello') =", len_of("hello"))

print()
print("================ 小结 ================")
print("1. 函数是为了「一次定义，到处复用」。")
print("2. 默认参数放在普通参数后面。")
print("3. 多返回值本质是元组，可以一次解包。")
print("4. *args 装成元组，**kwargs 装成字典。")
print("5. 默认参数千万别用 [] / {} / set()，要写 None。")
print("6. sorted(key=lambda ...) 用来按自己的规则排序。")
