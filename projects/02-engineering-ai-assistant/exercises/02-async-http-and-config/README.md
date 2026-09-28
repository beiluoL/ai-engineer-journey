# Exercises 02-async-http-and-config — M01 / M02 / M05 配套练习

> 对应：`milestones/01-async-await.md`（⬜ 未学习）、`milestones/02-async-http-client.md`（⬜ 未学习）、`milestones/05-config-and-environment.md`（⬜ 未学习）
> 规则：**亲手敲，不复制粘贴**。每题先自己写、跑通，再对照 milestone 里的示例。
> 勾选权在你手里：本文件所有复选框一律 ⬜，跑通的是「参考答案」，不是「你学会了」。

## A. async / await（Milestone 01）

- [ ] **A1** 写 `async def greet(name: str) -> str`(内部 `await asyncio.sleep(0)`)，再用 `asyncio.run` 跑它。
  验证：函数体里**一次同步阻塞调用都没有**；`greet("x")` 不调用时返回的是协程对象（打印 `type()` 看一眼）。

- [ ] **A2** 写 `async def chat_all(prompts, client) -> list[str]`，内部用 `asyncio.gather(*(... for p in prompts))` 并发发出。
  验证：把 `prompts` 换成 5 条，`client.chat` 被调用 5 次、返回结果顺序与输入顺序一致。

- [ ] **A3（核心）** 证明并发真的省时间 —— 定义一个「替身客户端」（`async def chat` 里只 `await asyncio.sleep(0.15)`，**不联网**），分别测：
  - 串行：一个 `async def` 里 `await` 三次；
  - 并发：`asyncio.gather` 同样的三次。
  打印两次真实墙钟耗时和 `并发耗时 / 串行耗时` 的比值，并断言这个比值 **> 1**（比值必须是这次跑出来的，不许写死）。

## B. 异步 HTTP 与测试替身（Milestone 02）

- [ ] **B1** 用仓库里现成的 `FakeClient`（`src/assistant/client.py`，不联网、可预设失败次数）跑 4 个并发 `chat`，断言 `fake.calls` 里记到了 4 条消息、返回列表顺序不变。
  验证：调用次数就是 4，`FakeClient` 上没有真的 socket。

- [ ] **B2** 用 `asyncio.wait_for(client.chat(...), timeout=0.05)` 给一次「慢请求」设超时。
  验证：抛出 `asyncio.TimeoutError`，且被取消的那一次**已经把消息记进了 `fake.calls`**（取消不等于没发请求）。

- [ ] **B3** 用 `FakeClient(fail_times=2)` 模拟「前两次限流、第三次成功」，自己写一个退避重试循环（退避用 `asyncio.sleep(0)`，不要真等）。
  验证：总共尝试 3 次、第 3 次拿到回复；再验证「超过重试次数后抛的是 `LLMRateLimitError`，且它能被 `LLMError` 基类捕获」。

## C. frozen 配置与环境（Milestone 05）

- [ ] **C1** 验证优先级 **真实环境变量 > .env 文件 > 代码默认值**：
  临时写一个 .env（内容自己编，注意别把自己的真实 Key 写进去），再在 `os.environ` 里预设一个**同名不同值**的变量，用 `Settings.from_env(dotenv_path=<临时路径>)` 读出来比对。
  验证：三个来源各取到该取的那一档；跑完把临时环境变量清理掉（`del os.environ[...]`，别污染后续命令）。

- [ ] **C2** 验证「frozen 配置在并发里也是安全的」：用 `asyncio.gather` 并发地对同一个 `Settings` 对象做 4 次 `dataclasses.replace(...)`（改 `log_level`），断言原对象一个字段都没变、4 个变体互不相同。

- [ ] **C3** 踩一遍校验失败：把 `DEEPSEEK_TIMEOUT` 设成非数字，调 `Settings.from_env(dotenv_path="")` 看抛什么；再用 `Settings(...).validate()` 验证 base_url 非法时也会抛 `LLMConfigError`。
  验证：两类错误都是 `LLMConfigError`，且错误信息里带上了当前值。

## 验收标准

A3 的比值必须真的 > 1（这是「异步到底省不省时间」的唯一硬证据）、B2 的超时真抛、C1 三档优先级逐一成立 = 这组对应章节过关。
看参考答案不算通过 —— 参考答案里的数字是它自己跑出来的，你得跑出你自己的数字。

## 参考答案与判卷

- 参考答案：`answers.py`（每题一个函数，纯离线）
- 怎么跑：
  ```bash
  .venv/bin/python exercises/02-async-http-and-config/answers.py
  ```
- 怎么判卷（全仓库一起判）：
  ```bash
  .venv/bin/python exercises/grade.py
  ```

> **重要**：`answers.py` 跑通只代表「参考答案跑通」。是否学会由你自己勾选，参考：[`../README.md`](../README.md)
