"""工具函数：把「打印 messages」这件事单独放这里。"""


def show(messages):
    """把一条 messages 打印成好看的样子。"""
    for i, m in enumerate(messages, start=1):
        print(f"   {i}. [{m['role']}] {m['content']}")


def now():
    """返回当前时间字符串（用来演示模块之间是可以互相调用的）。"""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
