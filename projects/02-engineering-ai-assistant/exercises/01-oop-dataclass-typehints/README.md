# Exercises 01-oop-dataclass-typehints — M00 / M03 / M04 / M05 配套练习

> 对应：`milestones/00-classes-and-oop.md`（⬜ 未学习）、`milestones/03-type-hints.md`（⬜ 未学习）、`milestones/04-dataclass.md`（⬜ 未学习）、`milestones/05-config-and-environment.md` 中「配置对象用 frozen dataclass」那一小节（⬜ 未学习）
> 规则：**亲手敲，不复制粘贴**。每题先自己写、跑通，再对照 milestone 里的示例。
> 勾选权在你手里：本文件所有复选框一律 ⬜，跑通的是「参考答案」，不是「你学会了」。

## A. 类与 OOP（Milestone 00）

- [ ] **A1** 手写（**不要用 dataclass**）一个类 `Turn(role, content)`：
  - `role` 只允许 `"system" / "user" / "assistant"`，非法值要抛 `ValueError`；
  - 加一个 `@property is_user`；加一个实例方法 `token_estimate()`（中文保守估算法：字符数 // 2）；
  - 加 `__repr__` 打印 `{内容字符数}` 而不是把正文全打出来（长正文会撑爆日志）；
  - 加 `__eq__`，且「和别的类型比较」不要炸（返回 `NotImplemented`）。
  验证：非法 role 会抛、估算值等于 `len(content) // 2`、`turn == "字符串"` 得到 `False` 而不是异常。

- [ ] **A2** 写一个封装对话历史的类 `Conversation`：内部状态放 `_turns`，用 `@property turns` **返回副本**，再实现 `__len__` 与 `token_estimate()`。
  验证：`c.turns.append(...)` 改不到内部状态；和仓库里真实的 `assistant/conversation.py` 的 `token_estimate()` 对同一组文本算出的数字一致。

- [ ] **A3** 说明并验证「组合优先于继承」：让 `Conversation` 持有 `Turn` 对象，而不继承 `Turn`；并验证 `Conversation.add` 是**绑定方法**（有 `__self__`），可以直接 `c.add` 传走而不用 `c.add(turn)`。

## B. 类型注解（Milestone 03）

- [ ] **B1** 写 `Optional[...]` 版的取消息函数：
  `def first_content(messages: Optional[list[dict[str, str]]] = None) -> Optional[str]`
  输入为空 / `None` 时返回 `None（不是空字符串）`，有内容时返回第一条的 `content`。
  验证：`typing.get_type_hints()` 能看到返回注解是 `Optional[str]`；空输入返回 `None`。

- [ ] **B2** 用**有界 TypeVar** 写泛型求和：
  ```python
  T = TypeVar("T", bound=<某个只声明 token_estimate() 的协议>)
  def total_tokens(items: Sequence[T]) -> int: ...
  ```
  验证：能同时吃下 A1 的 `Turn` 和另一个自己写的同类（不需要继承同一个基类），和是对的。

- [ ] **B3** 用 `runtime_checkable` 的 `Protocol` 做结构化类型：
  ```python
  @runtime_checkable
  class ChatLike(Protocol):
      def chat(self, messages: list[dict[str, str]]) -> str: ...
  ```
  验证：`assistant/client.py` 里的 `FakeClient`（它没有继承 `ChatLike`）能通过 `isinstance` 检查，而一个只有 `aclose()` 的对象不能。

## C. dataclass 与不可变配置（Milestone 04 + M05 片段）

- [ ] **C1** 写 `@dataclass(frozen=True)` 的 `ModelConfig(model, temperature, api_key)`：
  - `api_key` 用 `field(repr=False)`（repr 绝不打印密钥），并 `compare=False`（比较配置时不比密钥）；
  - 用 `__post_init__` 校验：`model` 非空、`0.0 <= temperature <= 2.0`，否则抛 `ValueError`；
  验证：改任意字段抛 `FrozenInstanceError`；`repr` 里搜不到密钥；两个只差密钥的实例 `==` 为 `True`；实例可 `hash()`。

- [ ] **C2** 用 `dataclasses.replace()` 改配置：把 `temperature` 从 0.7 改成 0.1、换 `model`，密钥保持不变。
  验证：原对象一个字段都没变、新旧对象不是同一个、`replace` 后的 `api_key` 与原对象相同。

- [ ] **C3** 对照仓库里真实的 `Settings`（`src/assistant/settings.py`）做反射验证：
  用 `dataclasses.fields()` 数出它有几个字段、`api_key` 的 `repr` 是不是 `False`、它是不是 frozen（`Settings.__dataclass_params__.frozen`），再用 `Settings(api_key=...).validate()` 验证「空密钥 / base_url 不合法 / timeout <= 0」三种情况确实抛 `LLMConfigError`。

## 验收标准

A1-A3 + B1-B3 + C1-C3 全部**自己写得出来并跑通** = 这一组对应的 M00 / M03 / M04 / M05 配置小节进入「能写代码」档。
看参考答案不算通过 —— 对照差异时请只打开卡住的那一两个函数。

## 参考答案与判卷

- 参考答案：`answers.py`（每题一个函数 `a1()` / `b2()` / ...，纯离线，无任何网络调用）
- 怎么跑：
  ```bash
  .venv/bin/python exercises/01-oop-dataclass-typehints/answers.py
  ```
- 怎么判卷（全仓库一起判）：
  ```bash
  .venv/bin/python exercises/grade.py
  ```
  判卷脚本会拦下任何「answers.py 里出现联网符号」的情况。

> **重要**：`answers.py` 跑通只代表「参考答案跑通」。是否学会由你自己勾选，参考：[`../README.md`](../README.md)
