from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
from urllib.request import Request as URLRequest

import pytest

from ie.serve import no_proxy_opener, start_server, stop_server


class FakeTokenizer:
    def encode(self, text):
        return [4 + ord(char) % 20 for char in text] or [4]

    def decode(self, ids, skip_special=False):
        return "".join(chr(97 + (int(token) % 26)) for token in ids if not skip_special or token > 3)


class FakeEngine:
    max_len = 128

    def generate_ids(self, prompt_ids, max_new_tokens, **_kwargs):
        return list(prompt_ids) + [4 + i % 10 for i in range(max_new_tokens)]


@pytest.fixture
def service():
    server, thread, url = start_server(FakeEngine(), FakeTokenizer(), port=0)
    yield server, url
    stop_server(server, thread)


def get(url):
    with no_proxy_opener().open(url, timeout=5) as response:
        return response.status, json.loads(response.read().decode())


def post(url, body):
    request = URLRequest(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with no_proxy_opener().open(request, timeout=5) as response:
        return response.status, response.read()


def body(max_tokens=3, stream=False, include_usage=False):
    return {
        "model": "test", "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": max_tokens, "stream": stream,
        "stream_options": {"include_usage": include_usage},
    }


def parse_sse(raw):
    return [line[6:] for line in raw.decode().splitlines() if line.startswith("data: ")]


def test_health_returns_200(service):
    _server, url = service
    status, payload = get(url + "/health")
    assert status == 200
    assert payload == {"status": "ok"}


def test_port_zero_allocates_real_port(service):
    server, _url = service
    assert server.server_address[1] > 0


def test_non_stream_schema(service):
    _server, url = service
    status, raw = post(url + "/v1/chat/completions", body(max_tokens=4))
    payload = json.loads(raw)
    assert status == 200
    assert payload["object"] == "chat.completion"
    assert payload["choices"][0]["message"]["role"] == "assistant"
    assert payload["usage"]["completion_tokens"] == 4


@pytest.mark.parametrize("include_usage,expected_json_chunks", [(False, 4), (True, 5)])
def test_sse_chunk_count_matches_stream_options(service, include_usage, expected_json_chunks):
    _server, url = service
    status, raw = post(url + "/v1/chat/completions", body(3, True, include_usage))
    lines = parse_sse(raw)
    assert status == 200
    assert lines[-1] == "[DONE]"
    assert len([line for line in lines if line != "[DONE]"]) == expected_json_chunks
    parsed = [json.loads(line) for line in lines if line != "[DONE]"]
    assert sum("usage" in item for item in parsed) == int(include_usage)


def test_metrics_count_requests_and_tokens(service):
    _server, url = service
    post(url + "/v1/chat/completions", body(2))
    post(url + "/v1/chat/completions", body(5))
    _status, metrics = get(url + "/metrics")
    assert metrics["requests"] == 2
    assert metrics["errors"] == 0
    assert metrics["generated_tokens"] == 7
    assert metrics["p95_latency_ms"] >= 0


def test_invalid_request_increments_errors(service):
    _server, url = service
    with pytest.raises(HTTPError) as caught:
        post(url + "/v1/chat/completions", body(0))
    assert caught.value.code == 400
    _status, metrics = get(url + "/metrics")
    assert metrics["requests"] == 1
    assert metrics["errors"] == 1


def test_concurrent_requests_all_succeed(service):
    _server, url = service
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(post, url + "/v1/chat/completions", body(2)) for _ in range(8)]
    results = [future.result() for future in futures]
    assert all(status == 200 for status, _raw in results)
    _status, metrics = get(url + "/metrics")
    assert metrics["requests"] == 8
    assert metrics["generated_tokens"] == 16


def test_unknown_route_returns_404(service):
    _server, url = service
    with pytest.raises(HTTPError) as caught:
        get(url + "/missing")
    assert caught.value.code == 404
