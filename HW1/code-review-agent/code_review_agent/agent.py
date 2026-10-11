"""Agent 核心：循环 = 输入 → 推理 → 工具调用 → 输出。

上下文记忆：messages 列表在整个会话中保留，
Agent 每一轮的工具调用结果也会进入记忆，供后续推理引用。
"""

import json
import logging

from .config import Config
from .llm import LLMClient
from .tools import Tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位资深代码审查专家（Code Reviewer）。你的任务是审查用户指定的代码，
找出潜在 Bug、代码质量问题和安全风险，并给出具体、可操作的改进建议。

工作方式：
1. 先用 list_files 了解项目结构，再用 read_file 阅读相关代码；必要时用 search_code
   定位某个符号的所有用法，或用 check_syntax 快速验证 Python 文件语法。
2. 你必须基于真实读到的代码给出结论，禁止臆测不存在的代码。
3. 工具调用要克制：优先审查用户明确指定的文件，按需扩展到其依赖。

最终输出（中文 Markdown）按以下结构：
## 总体评价
一两句话概括代码质量。

## 问题清单
按严重程度分组（🔴 严重 / 🟡 建议 / 🔵 风格），每个问题包含：
- 位置（文件:行号）
- 问题描述与影响
- 具体修改建议（附代码片段）

## 亮点
值得肯定的做法（如果有）。"""


class CodeReviewAgent:
    """代码审查智能体。"""

    def __init__(self, config: Config, root: str, prior_context: str = ""):
        self.config = config
        self.llm = LLMClient(config)
        self.tools = Tools(root, config.tool_output_limit)
        self.root = root
        # 上下文记忆：整个会话共享一份消息列表
        system = SYSTEM_PROMPT
        if prior_context:
            system += (
                "\n\n## 之前会话的背景\n"
                "以下是上一次审查的输出，可以引用其中的内容：\n\n"
                + prior_context
            )
        self.messages = [{"role": "system", "content": system}]

    # ---------- 核心循环 ----------

    def run(self, user_input: str, quiet: bool = False) -> str:
        """执行一轮完整的 Agent 循环，返回最终回复文本。"""
        self.messages.append({"role": "user", "content": user_input})

        for turn in range(1, self.config.max_turns + 1):
            message = self.llm.chat(self.messages, tools=self.tools.schemas)

            # 无工具调用 → 得到最终回答，循环结束
            if not message.tool_calls:
                reply = message.content or "（无输出）"
                self.messages.append({"role": "assistant", "content": reply})
                return reply

            # 记录助手这一轮的推理（含工具调用意图），维持上下文完整
            self.messages.append(message)

            # 依次执行每个工具调用，把结果喂回给 LLM
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                if not quiet:
                    print(f"  [工具] {name}({json.dumps(arguments, ensure_ascii=False)})")
                result = self.tools.execute(name, arguments)
                if not quiet:
                    print(f"  [结果] {result.splitlines()[0][:80]}")
                self.messages.append(
                    {"role": "tool", "tool_call_id": tool_call.id, "content": result}
                )

        return "已达到最大循环轮数，审查提前终止。请缩小审查范围后重试。"

    # ---------- 记忆管理 ----------

    def reset(self) -> None:
        """清空对话记忆（保留 system prompt），开始新的会话。"""
        self.messages = [self.messages[0]]
