"""服务化（M10）：健康检查、非流式、SSE 流式、错误码、并发压测。"""

from __future__ import annotations

from tiny.serve import ServingSession, load_test, smoke_test


def test_smoke_test_covers_four_paths(trained_bundle):
    cfg = trained_bundle["cfg"]
    with ServingSession(cfg, trained_bundle["model"], trained_bundle["tokenizer"]) as session:
        assert session.url.startswith("http://127.0.0.1:")
        result = smoke_test(session.url, "问：什么是 KV Cache？答：", max_tokens=6)
    assert result["health"]["status"] == 200
    assert result["non_stream"]["status"] == 200
    assert result["non_stream"]["usage"]["completion_tokens"] > 0
    assert result["stream"]["status"] == 200
    assert result["stream"]["token_events"] > 0
    assert result["stream"]["done"]
    assert result["bad_request"]["status"] == 400  # max_tokens=0 必须被拒
    assert result["passed"]


def test_load_test_all_requests_succeed(trained_bundle):
    cfg = trained_bundle["cfg"]
    prompts = ["问：什么是 LoRA？答：", "问：什么是幻觉？答：", "问：什么是早停？答："]
    with ServingSession(cfg, trained_bundle["model"], trained_bundle["tokenizer"]) as session:
        result = load_test(session.url, prompts, concurrency=3, max_tokens=6)
    assert result["all_ok"]
    assert result["requests"] == 3
    assert result["requests_per_sec"] > 0
    assert result["completion_tokens"] > 0


def test_server_stops_cleanly(trained_bundle):
    """``with`` 退出后线程必须结束，否则测试进程会挂住。"""
    import threading

    cfg = trained_bundle["cfg"]
    before = threading.active_count()
    with ServingSession(cfg, trained_bundle["model"], trained_bundle["tokenizer"]) as session:
        assert threading.active_count() > before
        url = session.url
    assert threading.active_count() <= before
    assert url
