# 02 结构化输出、流式与模型参数 — M03 / M04 / M06 配套练习

> 先独立完成，再按题号查看 `answers.py` 中对应函数。所有状态从 ⬜ 开始；参考答案跑通不代表你已掌握。

## A. 结构化输出（M03）

- [ ] **A1** 把裸 JSON、带 `json` 围栏的 JSON、前后夹解释文字的 JSON 分别交给真实 `assistant.schema.extract_json`，断言三次都得到同一个 Python 对象，并让完全无 JSON 的文本抛 `JSONDecodeError`。
- [ ] **A2** 用真实 `SkillExtraction.model_json_schema()` 检查 `name/skills/years/summary` 四个字段与 `years` 范围约束，再用 `parse_structured` 把合法 JSON 变成强类型对象并读取真实字段值。
- [ ] **A3** 把 `years="三年"` 的 JSON 交给真实 `parse_structured`，断言抛 `StructuredOutputError`、错误文本点名 `years`，且异常链 `__cause__` 保留 Pydantic 的 `ValidationError`。
- [ ] **A4** 用真实 `FakeClient` 编排“第一次字段错误、第二次正确”，调用真实异步 `structured(max_retry=1)`，断言恰好调用两次、第二次 messages 回灌校验错误、两次都启用 JSON Mode。

## B. 流式输出（M04）

- [ ] **B1** 用真实 `FakeClient.stream` 流出一段中英混排文本，逐块收集并断言拼接结果等于原回复、块数等于 Python 字符数，且调用记录标记了 `stream=True`。
- [ ] **B2** 用真实 `ChatService.astream` 与 `FakeClient` 完成一次流式问答，断言每块拼接成完整答案，并检查会话末尾已经回灌完整 assistant 内容而不是半截 chunk。
- [ ] **B3** 用 FastAPI `TestClient`、真实 `create_app()` 和依赖覆盖注入 `FakeClient`，离线 POST `/chat/stream`，断言 Content-Type 为 `text/event-stream`、每个 data JSON 可解析且最后出现 `data: [DONE]`。

## C. 模型参数（M06）

- [ ] **C1** 从同一个真实 `Settings(api_key="offline-test")` 生成 `extract` 与 `creative` Profile，断言原对象不变、新对象不是原对象，并比较两个 Profile 的真实 temperature/max_tokens。
- [ ] **C2** 只构造不请求真实 `DeepSeekClient`，调用 `build_payload` 检查 model/messages/stream/temperature/top_p/max_tokens/response_format/tools 全部进入请求体，再检查 `headers()` 不泄露测试 Key并关闭客户端。
- [ ] **C3** 把 temperature 越界、top_p 为 0、max_tokens 为 0 三个真实 `Settings` 逐一调用 `validate()`，断言都抛 `LLMConfigError` 且错误文本点名对应参数；合法配置应返回 `None`。

## 运行参考答案

```bash
.venv/bin/python exercises/02-structured-and-streaming/answers.py
```
