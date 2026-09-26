"""pkgdemo 包的说明书。

一个目录只要有一个 __init__.py，Python 就把它当成「包」。
这个文件会在 `import pkgdemo` 的时候自动执行一次。
"""

print("[pkgdemo/__init__.py] 我被执行了")

__version__ = "0.1.0"
