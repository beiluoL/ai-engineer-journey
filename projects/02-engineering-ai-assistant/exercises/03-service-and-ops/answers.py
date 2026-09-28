"""Exercises 03-service-and-ops 参考答案（对应 M06 / M07 / M08 / M09）。

用法:
    .venv/bin/python exercises/03-service-and-ops/answers.py

规矩:
    先自己把 11 题敲一遍、跑通了再来看这个文件。卡住了只看对应那一个函数，不要整份抄。
    本文件纯离线：不联网、不起真实端口、不读真实 API Key；FastAPI 一律走 TestClient。

判卷标记:
    每题跑完打印 "[PASS] <题号> <这次真的看到的东西>"，判卷脚本靠它计数。
"""

from __future__ import annotations

import importlib
import importlib.metadata
import io
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import traceback
from pathlib import Path

from assistant.client import FakeClient
from assistant.errors import LLMRateLimitError, LLMError
from assistant.logging_setup import JsonFormatter, TextFormatter, redact_headers
from assistant.service import AssistantService

# 本文件在 exercises/03-service-and-ops/ 下，往上三层才是项目根（pyproject.toml / src 都在那儿）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 题库里统一用这个打印过关标记，判卷脚本靠 "[PASS]" 这五个字符计数。
def _pass(qid: str, note: str) -> None:
    print(f"[PASS] {qid} {note}")


# ---------- A. 日志（Milestone 06） ----------

def a1() -> None:
    """A1: 从 setup_logging 的真实格式串反推正则，再解析一行真实日志。"""
    fmt = TextFormatter()._fmt          # "%(asctime)s %(levelname)-7s %(name)-22s %(message)s"
    datefmt = TextFormatter().datefmt   # "%H:%M:%S"
    print(f"  真实格式串 = {fmt!r}，datefmt = {datefmt!r}")

    time_re = r"[\d:]+"
    pattern = re.compile(
        r"^(?P<ts>\S+)\s+(?P<level>\w+)\s+(?P<name>.{22})\s(?P<msg>.*)$"
    )
    assert "%(asctime)s" in fmt and "%(levelname)" in fmt and "%(name)" in fmt

    # 造一行「长名字」的日志：name 字段被截到 22 字符，剩下的进消息
    logger = logging.getLogger("assistant.client")
    logger.setLevel(logging.INFO)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(TextFormatter())
    logger.addHandler(handler)
    logger.info("请求 LLM: model=deepseek-chat")
    line = buf.getvalue().strip()
    logger.removeHandler(handler)
    print(f"  真实一行 = {line}")

    m = pattern.match(line)
    assert m, "A1: 正则没匹配上真实日志行"
    fields = m.groupdict()
    print(f"  拆出来 = ts={fields['ts']!r} level={fields['level']!r} name={fields['name'].strip()!r} msg={fields['msg']!r}")
    assert fields["level"] == "INFO", "A1: 级别拆错了"
    assert fields["name"].strip() == "assistant.client"
    assert "deepseek-chat" in fields["msg"]

    # 格式不对的行：不要静默返回空字典，要么显式失败要么明确报错
    bad = pattern.match("这不是日志行")
    assert bad is None, "A1: 不该匹配到非法行"
    print("  非法行匹配结果是 None —— 调用方必须自己处理这种「解析不出来」的情况")

    _pass("A1", "从真实格式串反推的正则把一行日志拆成时间/级别/logger/消息，且能识别非法行")


def a2() -> None:
    """A2: 脱敏 —— 敏感 key 打码，原字典不被改。"""
    headers = {
        "Authorization": "Bearer sk-SECRET-9999",
        "X-Api-Key": "abc",
        "Content-Type": "application/json",
    }
    redacted = redact_headers(headers)

    for key in ("authorization", "api-key", "x-api-key"):
        print(f"  {key!r} 会被打码: {key in redact_headers({key: 'v'})}")
    print(f"  原样 = {headers['Content-Type']}")
    print(f"  打码后 = {redacted}")
    assert redacted["Authorization"] == "***"
    assert redacted["X-Api-Key"] == "***"
    assert redacted["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer sk-SECRET-9999", "A2: 原字典被改了（它应该返回新字典）"

    # 真实客户端发出的请求头也走一遍：Key 绝不能出现在日志里
    from assistant.client import DeepSeekClient
    from assistant.settings import Settings

    real = DeepSeekClient(Settings(api_key="sk-SECRET-9999"))
    real_redacted = redact_headers(dict(real._client.headers))
    print(f"  真实客户端请求头打码后 authorization = {real_redacted.get('authorization')!r}")
    assert "sk-SECRET-9999" not in str(real_redacted), "A2: 日志里泄露了 Key"
    assert real_redacted.get("authorization") == "***"
    assert real_redacted.get("content-type") == "application/json"
    import asyncio

    asyncio.run(real.aclose())

    # 大小写不敏感：AUTHORIZATION 也会被打码
    assert redact_headers({"AUTHORIZATION": "x"})["AUTHORIZATION"] == "***"

    _pass("A2", "Authorization / X-Api-Key（含大小写变体）变成 ***，原字典未改，真实客户端头也不泄露 Key")


def a3() -> None:
    """A3: JsonFormatter + extra_fields。"""
    buf = io.StringIO()
    logger = logging.getLogger("ex03.structured")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)

    logger.info("LLM 调用完成", extra={"extra_fields": {"model": "deepseek-chat", "prompt_tokens": 128}})
    logger.info("没有额外字段的普通日志")

    payloads = [json.loads(line) for line in buf.getvalue().strip().splitlines()]
    for p in payloads:
        print(f"  {json.dumps(p, ensure_ascii=False)}")
    first, second = payloads
    assert first["level"] == "INFO" and first["logger"] == "ex03.structured"
    assert first["model"] == "deepseek-chat" and first["prompt_tokens"] == 128
    assert "model" not in second, "A3: 没有 extra_fields 时不应出现这个键"
    logger.removeHandler(handler)

    _pass("A3", "结构化日志行能被 json.loads 回来，extra 字段被合并进去，无 extra 的行不产生空字段")


# ---------- B. 测试与调试（Milestone 07） ----------

TEST_FILE = '''
"""临时用例：用 FakeClient 给 AssistantService 写测试（不联网）。"""
from assistant.client import FakeClient
from assistant.service import AssistantService


def test_ask_returns_reply_and_grows_history():
    svc = AssistantService(FakeClient(reply="固定回答"), system_prompt="你是测试用的助手")
    answer = svc.ask_sync("你好")
    assert answer == "固定回答"
    history = svc.history
    assert [m["role"] for m in history] == ["system", "user", "assistant"], history
    assert history[-1]["content"] == "固定回答"
'''


def b1() -> None:
    """B1: 写一个 pytest 用例并真的跑绿。"""
    tmpdir = tempfile.mkdtemp(prefix="ex03-pytest-")
    test_path = os.path.join(tmpdir, "test_fake_service.py")
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(TEST_FILE)

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-q"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=180,
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:]
    print(f"  pytest 退出码 = {proc.returncode}，末行输出 = {tail[0] if tail else ''}")
    assert proc.returncode == 0, f"B1: 用例没跑绿\n{proc.stdout}\n{proc.stderr}"
    assert "passed" in proc.stdout, "B1: 输出里没看到 passed"

    # 反向验证：把断言写反，它必须报 fail（否则这个测试是摆设）
    bad_path = os.path.join(tmpdir, "test_deliberately_wrong.py")
    with open(bad_path, "w", encoding="utf-8") as f:
        f.write("def test_wrong():\n    assert 1 == 2\n")
    bad = subprocess.run(
        [sys.executable, "-m", "pytest", bad_path, "-q"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=180,
    )
    print(f"  故意写错的用例退出码 = {bad.returncode}（非 0 才说明测试真的在拦错误）")
    assert bad.returncode != 0

    shutil.rmtree(tmpdir, ignore_errors=True)   # pytest 会在里面留 __pycache__，别手动 rmdir

    _pass("B1", "自己写的用例用 pytest 跑出 passed；故意写反的用例确实 fail（测试真的在拦错误）")


def parse_answer(data: dict) -> str:
    """B2: 带异常链的解析。from e 是关键。"""
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError("响应格式不符合预期") from e


def b2() -> None:
    """B2: 异常链：根因不能丢。"""
    try:
        parse_answer({})
    except ValueError as e:
        print(f"  外层 = {type(e).__name__}: {e}")
        assert e.__cause__ is not None, "B2: 根因丢了"
        assert isinstance(e.__cause__, (KeyError, IndexError)), "B2: 根因类型不对"
        # from e 的两个副作用：__cause__ 指向根因，同时 __suppress_context__ 变 True
        # （= 打印时不再把原异常当「上下文」重复展示）。
        print(f"  __cause__ = {type(e.__cause__).__name__}: {e.__cause__}；__suppress_context__ = {e.__suppress_context__}")
        assert e.__suppress_context__ is True
        shown = traceback.format_exception(type(e), e, e.__traceback__)
        assert "direct cause of the following exception" in "".join(shown), "B2: traceback 没显示根因"
    else:  # pragma: no cover
        raise AssertionError("B2: 坏数据竟然没抛错")

    # 反例：不写 from，根因退到 __context__，追溯时容易被忽略
    try:
        try:
            {}["choices"]
        except KeyError:
            raise ValueError("没有 from 的写法")
    except ValueError as e:
        print(f"  没有 from 时：__cause__ = {e.__cause__}，__context__ = {type(e.__context__).__name__}")
        assert e.__cause__ is None and isinstance(e.__context__, KeyError)

    _pass("B2", "写了 from e 时 __cause__ 指向原始 KeyError 且 traceback 标出 direct cause；不写则退化成 __context__")


def b3() -> None:
    """B3: 失败路径也要断言。"""
    svc = AssistantService(FakeClient(reply="ok"))

    # 坑：ask() 是协程，只写 svc.ask("   ") 不会报错——它只是造了个协程没 await。
    # 想同步测就得用 ask_sync()（内部 asyncio.run）。
    try:
        svc.ask_sync("   ")
    except ValueError as e:
        print(f"  空白问题抛 {type(e).__name__}: {e}")
    else:  # pragma: no cover
        raise AssertionError("B3: 空白问题竟然没抛错")

    stuck = AssistantService(FakeClient(fail_times=99))
    try:
        stuck.ask_sync("触发限流")
    except LLMRateLimitError as e:
        print(f"  一直限流抛 {type(e).__name__}；是 LLMError 子类: {isinstance(e, LLMError)}")
        assert isinstance(e, LLMError)
    else:  # pragma: no cover
        raise AssertionError("B3: 限流竟然没抛错")

    # 正常路径仍然要绿
    assert svc.ask_sync("你好") == "ok"

    _pass("B3", "空白问题抛 ValueError；持续限流抛 LLMRateLimitError 且属 LLMError 子类")


# ---------- C. 打包（Milestone 08） ----------

def c1() -> None:
    """C1: 用 tomllib 读 pyproject.toml，并反射验证入口点。"""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]
    print(f"  name = {project['name']}，version = {project['version']}，requires-python = {project['requires-python']}")
    print(f"  dependencies = {project['dependencies']}")
    assert project["name"] == "engineering-ai-assistant"
    assert project["version"] and project["requires-python"]
    assert project["dependencies"], "C1: dependencies 不该是空的"

    entry = data["project"]["scripts"]["ai-assistant"]
    module_name, _, func_name = entry.partition(":")
    print(f"  入口点 ai-assistant = {entry}")
    assert func_name == "main", "C1: 入口点必须指向 main"

    module = importlib.import_module(module_name)
    src_file = Path(module.__file__)
    print(f"  入口点所在文件 = {src_file.relative_to(PROJECT_ROOT)}")
    assert src_file.exists(), "C1: 入口点文件不存在"
    assert callable(getattr(module, func_name)), "C1: 入口点文件里没有可调用的 main"
    print(f"  反射到 {module_name}.{func_name} = {getattr(module, func_name)}")

    _pass("C1", "pyproject 里的入口点 ai-assistant 真的指向 src 中存在的 main()，靠反射验证而非读文档")


def c2() -> None:
    """C2: 反射包结构 + 确认包已安装。"""
    import assistant

    exported = assistant.__all__
    missing = [name for name in exported if not hasattr(assistant, name)]
    print(f"  assistant.__all__ 共 {len(exported)} 个名字，取不到的 = {missing}")
    assert not missing, f"C2: __all__ 里有导不出的名字: {missing}"

    version = importlib.metadata.version("engineering-ai-assistant")
    print(f"  importlib.metadata.version() = {version}（说明包真的被安装过，不只是躺在 src 里）")
    assert version

    _pass("C2", f"__all__ 里 {len(exported)} 个名字全部可导出，且 importlib.metadata 读到安装版本 {version}")


# ---------- D. FastAPI（Milestone 09） ----------

class ExplodingClient(FakeClient):
    """D3: 一问就限流的替身（继承仓库自带的 FakeClient，不联网）。"""

    async def chat(self, messages: list[dict[str, str]]) -> str:
        raise LLMRateLimitError("模拟限流：429")


def d1() -> None:
    """D1: TestClient 打 /health 与 /chat，依赖注入换成 Fake。"""
    from fastapi.testclient import TestClient

    from assistant.api import app, get_service

    svc = AssistantService(FakeClient(reply="这是 FakeClient 的固定回答"), system_prompt="测试")
    app.dependency_overrides[get_service] = lambda: svc
    try:
        client = TestClient(app)     # 故意不用 with：不触发 lifespan，也就不需要真实 API Key
        health = client.get("/health")
        print(f"  GET /health -> {health.status_code} {health.json()}")
        assert health.status_code == 200 and health.json() == {"status": "ok"}

        resp = client.post("/chat", json={"message": "你好"})
        print(f"  POST /chat -> {resp.status_code} {resp.json()}")
        assert resp.status_code == 200
        assert resp.json()["reply"] == "这是 FakeClient 的固定回答"
    finally:
        app.dependency_overrides.clear()

    _pass("D1", "TestClient 下 /health 返回 ok，/chat 返回 FakeClient 的固定回答（全程无端口、无网络）")


def d2() -> None:
    """D2: Pydantic 入参校验由框架负责。"""
    from fastapi.testclient import TestClient

    from assistant.api import app, get_service

    svc = AssistantService(FakeClient(reply="回答"), system_prompt="测试")
    app.dependency_overrides[get_service] = lambda: svc
    try:
        client = TestClient(app)
        empty = client.post("/chat", json={"message": ""})
        print(f"  空消息 -> {empty.status_code}，loc = {empty.json()['detail'][0]['loc']}")
        assert empty.status_code == 422
        assert empty.json()["detail"][0]["loc"] == ["body", "message"]

        too_long = client.post("/chat", json={"message": "x" * 4001})
        print(f"  超长消息 -> {too_long.status_code}（min_length/max_length 都是写在模型里的）")
        assert too_long.status_code == 422
    finally:
        app.dependency_overrides.clear()

    _pass("D2", "空消息与超长消息都被 Pydantic 拦下：422 且错误定位在 body.message")


def d3() -> None:
    """D3: LLMError -> HTTP 502 的映射。"""
    from fastapi.testclient import TestClient

    from assistant.api import app, get_service

    svc = AssistantService(ExplodingClient(), system_prompt="测试")
    app.dependency_overrides[get_service] = lambda: svc
    try:
        client = TestClient(app)
        resp = client.post("/chat", json={"message": "触发限流"})
        body = resp.json()
        print(f"  限流时的 /chat -> {resp.status_code}，detail = {body['detail'][:40]}...")
        assert resp.status_code == 502, "D3: LLMError 应映射成 502"
        assert "限流" in body["detail"]
    finally:
        app.dependency_overrides.clear()

    _pass("D3", "底层抛 LLMRateLimitError 时 /chat 返回 502，detail 里带着原因")


def main() -> None:
    print("--- A ---")
    a1()
    a2()
    a3()

    print("\n--- B ---")
    b1()
    b2()
    b3()

    print("\n--- C ---")
    c1()
    c2()

    print("\n--- D ---")
    d1()
    d2()
    d3()

    print(f"\n全部 11 题跑完，退出码 0（Python {sys.version.split()[0]}）")


if __name__ == "__main__":
    main()
