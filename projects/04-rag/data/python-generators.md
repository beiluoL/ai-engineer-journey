# Python 生成器：惰性计算与内存

## 生成器是什么

生成器（generator）是一种「边算边吐」的迭代器。它和普通函数的区别只有两个关键字：
函数体里出现 `yield`，这个函数就不再是普通函数，而是返回一个生成器对象。

```python
def gen():
    for i in range(1000000):
        yield i * 2

g = gen()          # 注意：这里函数体一行都没执行
print(next(g))     # 0
print(next(g))     # 2
```

调用 `gen()` 不会执行函数体，只会造出一个生成器对象；第一次 `next(g)` 才开始跑，
一直跑到 `yield` 就停下，把 `yield` 后面的值交出去，等下一次 `next` 再从那里继续。
这种「执行到一半挂起、再次被唤醒」的能力叫协同程序（coroutine）的雏形。

## 为什么能省内存

`range(1000000)` 和 `[i * 2 for i in range(1000000)]` 差得不是一点点：
列表推导式会**一次性把 100 万个整数全部造出来**放在内存里，占用几十 MB；
生成器只在被调用的那一刻算出一个值，算完就丢，内存占用是常量级。

```text
列表推导式：  内存里同时存在 100 万个对象        时间换空间里的「空间」那一项很贵
生成器表达式：任何时刻内存里只有 1 个对象        代价是只能遍历一次
```

所以判断标准很简单：**你要的是「一整份结果」还是「一次一个的结果」**。
要排序、要 `len()`、要切片、要反复遍历 → 用列表；
只是一次流过来、算完就用 → 用生成器。

## yield from 与生成器嵌套

生成器可以互相委托，`yield from` 会把内层生成器的每一个值原样转发出来：

```python
def flat(nested):
    for item in nested:
        if isinstance(item, list):
            yield from flat(item)     # 递归展开
        else:
            yield item
```

## 生成器表达式

和列表推导式只差一对圆括号，其余语义完全一致：

```python
total = sum(x * x for x in range(10))     # 生成器表达式
pairs = ((a, b) for a in "ab" for b in "12")
```

## 常见坑

1. **生成器只能遍历一次**：遍历完后想重新用，得重新调用生成它的函数。
   需要反复遍历就自己 `list(g)` 缓存一份。
2. **`yield` 里的异常不会凭空消失**：在生成器内部 `try/except` 能捕获，
   但生成器被 `close()` 时会抛 `GeneratorExit`。
3. **不要在生成器里做有副作用的重活**：它可能在任何一行被暂停，
   调试时「执行到哪了」会变得不直观。

## 和 Java 的类比

Java 里对应的是 `Stream`（`Stream.generate` / `Iterable` 的惰性求值）与
`Iterator` 的 `next()` 协议：两者都是「消费者拉一个、生产者造一个」。
区别是 Java 的 Stream 更强调声明式管道，而 Python 生成器就是普通的迭代器实现。
