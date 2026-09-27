"""命令行入口的回归测试。

这一整个文件都是为 CLAUDE-GOTCHA 写的：

    ToolRegistry.schemas() 从「返回内层 function 对象」改成「返回完整工具对象」
    之后，cli.py 里还在按内层的 name/parameters 读 —— --list-tools 直接
    KeyError: 'parameters'。测试只覆盖了「发给模型的那一处」调用点，
    命令行的那一处没人看，于是真实运行第一下就炸。

从这个教训反推出的规则：**改一个被多处使用的结构，回归测试要覆盖每一处调用点，
而不是只覆盖你认为重要的那一处。**
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

import pytest

from agent.cli import build_llm, main, mock_responder
from agent.llm import FakeLLM
from agent.settings import AgentSettings


def _capsys_main(argv):
    """跑一次 main 并同时抓 stdout（capsys 抓不到 print 出来的子进程式输出）。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(argv)
    return code, buf.getvalue()


class TestListTools:
    """--list-tools 必须能读出完整工具对象的内层字段。"""

    def test_prints_every_registered_tool(self):
        code, out = _capsys_main(["--list-tools"])
        assert code == 0
        assert "calculator" in out
        assert "now" in out
        assert "rag_search" in out

    def test_reads_name_from_outer_wrapper(self):
        """回归：schemas() 返回 {"type":..,"function":{...}} 时必须拆一层。"""
        code, out = _capsys_main(["--list-tools"])
        assert code == 0
        # 曾经在这里 KeyError: 'parameters'，因为读的是 s["parameters"] 而不是 s["function"]["parameters"]
        assert "（expression）" in out
        assert "必填：query" in out

    def test_no_parameter_tool_shows_placeholder(self):
        code, out = _capsys_main(["--list-tools"])
        assert code == 0
        assert "now（无参数）" in out


class TestBuildLLM:
    """没有 Key 时降级而不是崩。"""

    def test_no_key_falls_back_to_fake(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        llm, real = build_llm(AgentSettings(), mock=False)
        assert real is False
        assert isinstance(llm, FakeLLM)

    def test_mock_flag_short_circuits(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
        llm, real = build_llm(AgentSettings(), mock=True)
        assert real is False
        assert isinstance(llm, FakeLLM)

    def test_question_only_flags(self):
        """--mock 之后的运行不联网：离线剧本能跑完一句话。"""
        code, out = _capsys_main(["--mock", "Project 04 的会话是怎么落盘的？"])
        assert code == 0
        assert "离线剧本" in out
        assert "答案：" in out


class TestTraceFlag:
    """--trace 接的是**目录**，落盘文件名由问题内容派生。"""

    def test_trace_writes_json(self, monkeypatch, workdir):
        monkeypatch.chdir(workdir)
        outdir = workdir / "traces"
        code, _ = _capsys_main(["--mock", "--trace", str(outdir), "现在几点？"])
        assert code == 0
        files = list(outdir.glob("*.json"))
        assert len(files) == 1
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        assert payload["answer"].strip()

    def test_no_leftover_temp_file(self, monkeypatch, workdir):
        monkeypatch.chdir(workdir)
        outdir = workdir / "traces"
        code, _ = _capsys_main(["--mock", "--trace", str(outdir), "现在几点？"])
        assert code == 0
        assert list(outdir.glob(".trace-*")) == []

    def test_without_trace_no_file(self, monkeypatch, workdir):
        monkeypatch.chdir(workdir)
        code, _ = _capsys_main(["--mock", "现在几点？"])
        assert code == 0
        assert list(workdir.glob("*.json")) == []


class TestNoQuestion:
    def test_missing_question_returns_2(self, capsys):
        code = main([])
        assert code == 2
        assert "usage" in capsys.readouterr().out


class TestMockResponder:
    """离线剧本的确定性：同一条消息走两遍结果一致（截图才对得上）。"""

    def test_deterministic(self):
        def once():
            llm = FakeLLM(responder=mock_responder())
            reply = llm.chat([])
            assert reply.tool_calls and reply.tool_calls[0].name == "rag_search"
            return reply.tool_calls[0]

        assert once() == once()

    def test_second_round_answers_from_tool_output(self):
        """第二轮必须**只吃 tool 消息里的内容**，正好演示 tool 结果回灌。"""
        llm = FakeLLM(responder=mock_responder())
        round_one = llm.chat([])
        assert round_one.tool_calls

        # 手工拼出第 2 轮的输入：assistant(带 tool_calls) + tool(结果)
        from agent.llm import LLMMessage
        from agent.tools import ToolResult

        call = round_one.tool_calls[0]
        result = ToolResult(call_id=call.id, name=call.name, output="[1] 假证据：落盘走 os.replace")
        messages = [round_one, LLMMessage(role="tool", content=result.render(), tool_call_id=call.id, name=call.name)]

        followup = llm.chat(messages)
        assert followup.content.startswith("查到了：")
        assert "[1] 假证据" in followup.content
        assert "唯一的依据" in followup.content
        # 关键：第二轮不再发起工具调用，直接出答案
        assert followup.tool_calls is None
