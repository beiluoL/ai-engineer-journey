# 11 — Class：类

## 它是什么
面向对象编程的基本单元。Python 类比 Java 类简洁得多：没有接口强制、没有访问修饰符、不用 new。

## Java 开发者如何理解

```java
// Java
public class LLMClient {
    private final String apiKey;                       // private 强制
    public LLMClient(String apiKey) { this.apiKey = apiKey; }
    public String ask(String q) { return "..."; }
}
// LLMClient c = new LLMClient("sk-...");
```

```python
# Python
class LLMClient:
    def __init__(self, api_key: str) -> None:   # __init__ = 构造器；self = this，必须显式写
        self.api_key = api_key                  # 公开属性（下划线开头=约定私有）

    def ask(self, question: str) -> str:        # 每个方法第一个参数都是 self
        return "..."

# client = LLMClient("sk-...")                  # 不要 new
```

**三大差异（务必刻进脑子）**：
1. `self` 必须显式写在每个实例方法第一个参数，调用时不传（Python 自动传）。
2. 没有真正的 private：`_name` 只是约定，语言不强制（Java 的 private 是强制的）。
3. 没有接口概念，靠**鸭子类型**：不看类型看行为——"会 ask 就是 client"。

## 最小可运行 Demo

```python
# demo_class.py —— Project 01 LLMClient 的教学版骨架
class LLMClient:
    """封装 LLM API 调用。v0.1 用假实现，之后换成真实 HTTP。"""

    def __init__(self, api_key: str, model: str = "deepseek-chat") -> None:
        if not api_key:
            raise ValueError("API Key 不能为空")
        self.api_key = api_key
        self.model = model

    def build_payload(self, question: str) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": question}],
        }

    def ask(self, question: str) -> str:
        payload = self.build_payload(question)
        return f"[假实现] 将以 model={payload['model']} 回答: {question}"


if __name__ == "__main__":
    client = LLMClient(api_key="sk-demo", model="deepseek-chat")
    print(client.ask("什么是 Attention？"))
```

## 常见错误

1. **忘写 self**：`def ask(question)` 然后实例调用 → `TypeError: takes 1 positional argument but 2 were given`（隐式把实例传给了 question）。方法第一个参数永远是 self。
2. **调用时多传 self**：`client.ask(client, "hi")` ❌。
3. **类属性 vs 实例属性混淆**：写在类体里的是所有实例共享（类似 Java static），写在 `__init__` 里 `self.x = ...` 才是实例私有。
4. **构造器名写错**：是 `__init__`（双下划线），写成 `_init_` 不会报错但永远不执行——极难排查。

## 常见面试问题
- Python 有真正的 private 吗？→ 没有，`__name`（双下划线）触发名称改写（name mangling），但只是变形不是隔离。
- `@staticmethod` / `@classmethod`？→ 静态方法无 self（同 Java static）；类方法第一个参数是类本身 `cls`，常用于替代构造器。
- dataclass？→ `@dataclass` 自动生成 `__init__`/`__repr__` 等，像 Java 的 Lombok/record。

## 练习
1. 把 demo_class.py 手敲跑通。
2. 给 LLMClient 加 `chat(messages: list[dict]) -> str` 方法。
3. 用 `@dataclass` 重写一个 `Message(role, content)` 类并打印。

[下一课：12-exception →](12-exception.md)
