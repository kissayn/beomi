"""LLM 客户端：封装 DeepSeek（OpenAI 兼容）接口，带指数退避重试。"""

import logging
import time

from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError

from .config import Config

logger = logging.getLogger(__name__)

# 可安全重试的错误类型（网络抖动 / 限流 / 服务端临时故障）
RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError)
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class LLMClient:
    """带重试机制的 LLM 客户端。"""

    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=120,
        )

    def chat(self, messages, tools=None):
        """调用 LLM，返回第一条回复消息。

        遇到限流 / 网络错误 / 服务端临时故障时指数退避重试。
        """
        for attempt in range(1, self.config.max_retries + 1):
            try:
                kwargs = {"model": self.config.model, "messages": messages}
                if tools:
                    kwargs["tools"] = tools
                resp = self.client.chat.completions.create(**kwargs)
                return resp.choices[0].message
            except RETRYABLE_ERRORS as e:
                self._wait_or_raise(attempt, e)
            except APIStatusError as e:
                if e.status_code in RETRYABLE_STATUS:
                    self._wait_or_raise(attempt, e)
                raise
        raise RuntimeError("LLM 调用重试次数已耗尽")

    @staticmethod
    def _wait_or_raise(attempt: int, err: Exception) -> None:
        """指数退避：1s, 2s, 4s ... 超过最大次数则抛出原始异常。"""
        wait = 2 ** (attempt - 1)
        logger.warning(
            "LLM 调用失败（第 %d 次）：%s，%d 秒后重试", attempt, err, wait
        )
        time.sleep(wait)
