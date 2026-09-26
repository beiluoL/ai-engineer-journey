# Python 的 GIL 与多线程

## GIL 是什么

GIL（Global Interpreter Lock，全局解释器锁）是 CPython 的一个互斥锁：
**任何时刻只有一个线程能执行 Python 字节码**。

它的存在有一个历史原因：CPython 的内存管理（引用计数）不是线程安全的，
如果去掉 GIL，就得给每个对象加锁，单线程性能反而会掉。所以 CPython 选择了
「一把大锁保护全部字节码」。Python 3.13 引入的 free-threading 版本才真正拿掉它。

## 两个后果

```text
CPU 密集任务：多线程「互相抢锁」，总耗时可能比单线程还慢
IO 密集任务：等待期间线程让出 GIL，多线程能显著提速
```

## 实测对比

```python
import threading

def cpu_work(n):
    total = 0
    for i in range(n):
        total += i * i          # 纯计算，不 IO
    return total

# 单线程：串行跑完
# 多线程：两个线程抢同一把 GIL，实际是来回切换，总耗时接近甚至高于串行
```

结论不是「多线程没用」，而是「**看任务类型**」：

| 任务类型 | 推荐手段 |
|---------|---------|
| CPU 密集（计算、图像处理、正则） | `multiprocessing` / `ProcessPoolExecutor` |
| IO 密集（HTTP、磁盘、数据库等待） | `threading` / `asyncio` |

## 绕过 GIL 的三条路

1. **`multiprocessing`**：每个进程一个独立的解释器、独立的 GIL，
   代价是内存不共享，通信要靠 `Queue` / `Pipe` / 共享内存。
   Java 类比：这就像是绕开 JVM 的单机模型，直接开多个 JVM 进程。
2. **把重活丢给底层库**：NumPy 的向量运算、pandas 的很多算子、
   `librosa` 之类 C/C++ 扩展在执行时**会释放 GIL**，所以多线程调它们是有效的。
3. **`asyncio`**：单线程里用事件循环切换协程，和 GIL 无关，
   适合大量短 IO 等待的场景（但一个耗时同步函数照样会卡住整个循环）。

## 常见坑

1. **用多线程算 CPU 密集合，然后困惑为什么变慢了**：先问自己「等待还是计算」。
2. **以为 `os.cpu_count()` 个线程就能榨满 CPU**：进程数才对应核数，
   线程只是并发的调度单位。
3. **在 `asyncio` 里跑同步重活**：整个事件循环会被阻塞，
   该扔进 `run_in_executor` 或 `ProcessPoolExecutor`。
