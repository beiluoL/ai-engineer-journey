# Exercises 03-service-and-ops — M06 / M07 / M08 / M09 配套练习

> 对应：`milestones/06-logging.md`（⬜ 未学习）、`milestones/07-testing-and-debugging.md`（⬜ 未学习）、`milestones/08-packaging.md`（⬜ 未学习）、`milestones/09-fastapi.md`（⬜ 未学习）
> 规则：**亲手敲，不复制粘贴**。每题先自己写、跑通，再对照 milestone 里的示例。
> 勾选权在你手里：本文件所有复选框一律 ⬜，跑通的是「参考答案」，不是「你学会了」。

## A. 日志（Milestone 06）

- [ ] **A1** 解析日志行。`setup_logging()` 用的格式串是
  `"%(asctime)s %(levelname)-7s %(name)-22s %(message)s"`（`datefmt="%H:%M:%S"`）。
  写正则把一行日志拆成 `{时间, 级别, logger 名, 消息}`，并断言拆出来的级别真的是 `INFO`。
  验证：拿一行真实日志去拆；再用一行格式不对的日志验证「匹配失败时你该怎么办」（不要静默返回空字典）。

- [ ] **A2** 脱敏。读 `src/assistant/logging_setup.py` 里的 `redact_headers()`，自己做一遍：
  `{"Authorization": "Bearer sk-xxx", "X-Api-Key": "abc", "Content-Type": "application/json"}`
  断言 `Authorization` / `X-Api-Key` 被打成 `***`，其它原样，且**原字典没被改**（它返回的是新字典）。
  再验证：这个函数会匹配哪些 key（大小写、连字符），列出来。

- [ ] **A3** 结构化日志。用 `JsonFormatter` 写一个 logger，挂 `StringIO` handler，`logger.info("LLM 调用完成", extra={"extra_fields": {...}})`，
  把输出行 `json.loads` 回来，断言里面有 `ts / level / logger / msg` 和你塞进去的自定义字段。
  验证：故意塞一个「没有 extra_fields」的日志行，看它是否被跳过（而不是变成 `null`）。

## B. 测试与调试（Milestone 07）

- [ ] **B1** 写一个**真的用 pytest 跑绿**的用例：用 `FakeClient` + `AssistantService`，断言「问一句 → 拿到固定回答 → 历史里多了两条消息」。
  Requirements：把用例写进临时目录的 `test_xxx.py`，用 `sys.executable -m pytest` 真跑一遍，断言退出码为 0 且输出里出现了 `passed`。
  验证：故意把断言写反，确认它真的会 fail（这一步是体会「测试为什么有价值」）。

- [ ] **B2** 异常链。写一个 `parse_answer()`：里面先访问 `data["choices"][0]["message"]["content"]`，捕获 `(KeyError, IndexError, TypeError)` 后 `raise ValueError("响应格式不对") from e`。
  断言：`ValueError.__cause__` 就是那个原始异常，`__suppress_context__` 为 `False`；
  再对比「不写 `from` 的写法」，指出那种写法丢掉了什么。

- [ ] **B3** 失败路径也要断言：
  - `service.ask("   ")`（纯空白）应抛 `ValueError`；
  - 用 `FakeClient(fail_times=99)` 时，`service.ask("xxx")` 抛的应是 `LLMRateLimitError`，并且它是 `LLMError` 的子类。
  验证：两条都真的抛，且异常类型逐级对得上。

## C. 打包（Milestone 08）

- [ ] **C1** 用 `tomllib` 读 `pyproject.toml`，断言：`name` / `version` / `requires-python` / `dependencies` 都在，
  `[project.scripts]` 里的入口点 `ai-assistant` 指向的 `assistant.cli:main` **这个文件存在且真的定义了 `main`**。
  验证：入口点这件事不靠读文档，靠反射验证。

- [ ] **C2** 反射包结构：`assistant.__all__` 里的每个名字都能 `getattr` 到；再用 `importlib.metadata.version(<包名>)` 验证这个包真的被安装过了。
  验证：数一数 `__all__` 里有几个名字，全部可导出。

## D. FastAPI（Milestone 09）

- [ ] **D1** 用 `TestClient` 打 `/health` 和 `/chat`：把 `get_service` 依赖 `override` 成「`FakeClient` 驱动的 service」，**不启真实端口、不触发 lifespan**。
  验证：`/health` 返回 `{"status": "ok"}`；`/chat` 返回 200 且 `reply` 就是 `FakeClient` 的固定回答。

- [ ] **D2** 入参校验：POST `/chat` 传 `{"message": ""}`。
  验证：返回 422，且 `detail[0]["loc"] == ["body", "message"]` —— 这是 Pydantic 给的，不是你写的。

- [ ] **D3** 错误映射：让依赖返回的是一个「一问就抛 `LLMRateLimitError`」的 service。
  验证：`/chat` 返回 **502**，且 `detail` 里带着错误原因（`api.py` 里把 `LLMError` 映射到 502 的那一层）。

## 验收标准

A1-A3 + B1-B3 + C1-C2 + D1-D3 全部自己写得出来并跑通 = 这组对应章节进入「能写代码」档。
特别要求：B1 必须是**你自己写的用例**跑出来的绿，看参考答案不算。

## 参考答案与判卷

- 参考答案：`answers.py`（每题一个函数，纯离线，FastAPI 那几题一律走 `TestClient`）
- 怎么跑：
  ```bash
  .venv/bin/python exercises/03-service-and-ops/answers.py
  ```
- 怎么判卷（全仓库一起判）：
  ```bash
  .venv/bin/python exercises/grade.py
  ```

> **重要**：`answers.py` 跑通只代表「参考答案跑通」。是否学会由你自己勾选，参考：[`../README.md`](../README.md)
