"""配置模块：从环境变量 / .env 读取配置。"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()  # 读取项目根目录下的 .env


@dataclass
class Config:
    """全局配置。"""

    api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    model: str = field(
        default_factory=lambda: os.getenv("CODE_REVIEW_MODEL", "deepseek-chat")
    )
    base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    )
    # API 调用失败时的最大重试次数
    max_retries: int = 3
    # 单个工具结果的长度上限（防止撑爆上下文）
    tool_output_limit: int = 15000
    # Agent 循环的最大轮数（防止死循环烧 token）
    max_turns: int = 15

    def validate(self) -> None:
        """检查必要配置是否齐全。"""
        if not self.api_key:
            raise SystemExit(
                "未配置 DEEPSEEK_API_KEY。\n"
                "请复制 .env.example 为 .env 并填入你的 Key，\n"
                "申请地址: https://platform.deepseek.com/"
            )
