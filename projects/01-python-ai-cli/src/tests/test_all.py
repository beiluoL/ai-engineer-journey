"""tests —— Project 01 单元测试（unittest，零第三方依赖）。

运行方式（在 projects/01-python-ai-cli 目录下）：
    python -m unittest discover -s tests -v
"""

import unittest

from assistant.config import Config, load_config
from assistant.errors import LLMConfigError, LLMRateLimitError, LLMResponseError
from assistant.client import DEFAULT_SYSTEM_PROMPT, LLMClient


class ConfigTest(unittest.TestCase):
    def test_missing_key_raises(self) -> None:
        # 不存在 .env 且无环境变量时应给出配置错误
        with self.assertRaises(LLMConfigError):
            load_config(env_file=".__no_such_env_file__")

    def test_dotenv_and_env_priority(self) -> None:
        import os, tempfile, pathlib
        tmp = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8")
        tmp.write("DEEPSEEK_API_KEY=sk-from-file\nDEFAULT_MODEL=model-from-file\n")
        tmp.close()

        # 环境变量优先于 .env 文件
        os.environ["DEEPSEEK_API_KEY"] = "sk-from-env"
        try:
            cfg = load_config(env_file=tmp.name)
            self.assertEqual(cfg.api_key, "sk-from-env")
            self.assertEqual(cfg.model, "model-from-file")
        finally:
            os.environ.pop("DEEPSEEK_API_KEY", None)
            pathlib.Path(tmp.name).unlink()


class LLMClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = LLMClient(Config(api_key="sk-test"))

    def test_build_payload(self) -> None:
        payload = self.client.build_payload("你好")
        self.assertEqual(payload["model"], "deepseek-chat")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][0]["content"], DEFAULT_SYSTEM_PROMPT)
        self.assertEqual(payload["messages"][-1], {"role": "user", "content": "你好"})

    def test_parse_answer(self) -> None:
        fake = {"choices": [{"message": {"role": "assistant", "content": "这是回答"}}]}
        self.assertEqual(LLMClient.parse_answer(fake), "这是回答")

    def test_parse_answer_bad_format(self) -> None:
        with self.assertRaises(LLMResponseError):
            LLMClient.parse_answer({"unexpected": True})

    def test_raise_for_status_mapping(self) -> None:
        with self.assertRaises(LLMRateLimitError):
            self.client._raise_for_status(429, "rate limited")
        with self.assertRaises(LLMResponseError):
            self.client._raise_for_status(500, "server error")


if __name__ == "__main__":
    unittest.main()
