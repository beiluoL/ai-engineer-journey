# Python 装饰器与闭包

## 闭包：装饰器的人力基础

闭包（closure）指的是「函数 + 它定义时捕获的外层变量」组成的整体。
关键是**变量捕获的是变量本身，不是值的快照**：

```python
def make_counter():
    count = 0
    def counter():
        nonlocal count
        count += 1
        return count
    return counter          # 返回的函数带着 count 一起活下来了

c = make_counter()
print(c(), c(), c())        # 1 2 3
```

`count` 是 `make_counter` 的局部变量，按理说函数返回就该被回收；
但 `counter` 引用了它，Python 的引用计数会把这段环境一起留住。
Java 里对应的是「匿名内部类 / lambda 捕获的 effectively final 局部变量」。

## 装饰器就是闭包 + 高阶函数

装饰器的本质：接受一个函数，返回一个替代它的函数。

```python
import time

def timer(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        print(f"{func.__name__} 耗时 {time.perf_counter() - start:.3f}s")
        return result
    return wrapper

@timer
def slow_add(a, b):
    time.sleep(0.1)
    return a + b
```

写装饰器的三条纪律：

1. **用 `*args, **kwargs` 转发**：否则只能装饰签名完全匹配的函数。
2. **`functools.wraps` 保留元信息**：被装饰的函数会丢掉 `__name__`、`__doc__`，
   `functools.wraps(func)` 把它们的引用原样拷到 wrapper 上，文档和 IDE 才不迷路。
3. **别在装饰器里吞异常**：应该 `try/except` 后记录、再重新抛出。

## 带参数的装饰器：三层嵌套

```python
import functools

def retry(times=3, delay=0.5):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last = None
            for i in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last = e
                    time.sleep(delay * (i + 1))
            raise last
        return wrapper
    return decorator

@retry(times=3)
def call_api(): ...
```

三层嵌套的原因一句话：`@retry(times=3)` 先被求值出 `decorator`，
再被套到函数上。缺任何一层都拿不到「参数」这一步。

## 类装饰器与带状态的装饰器

函数也能当装饰器用，需要保存状态时换类更清楚：

```python
class CallCount:
    def __init__(self, func):
        self.func = func
        self.calls = 0
        functools.update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        self.calls += 1
        print(f"调用第 {self.calls} 次")
        return self.func(*args, **kwargs)
```

## 常见坑

1. **装饰顺序**：`@a` 在最上面、`@b` 在下面时，实际生效是 b(a(func))，
   也就是先被 b 包裹。调试日志时要留意。
2. **给函数加参数导致签名变化**：用 `functools.wraps` 只是复制元信息，
   参数校验仍要靠 `*args, **kwargs` 转发。
3. **装饰器在 import 时执行**：模块级被装饰的函数在 import 阶段就完成包裹，
   所以装饰器里的副作用（建连接、写文件）会随 import 发生。
