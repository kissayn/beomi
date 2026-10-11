"""命令行入口。

用法：
  python main.py review <文件或目录>        # 一次性审查，输出 Markdown 报告
  python main.py review <路径> -o report.md # 同时保存报告到文件
  python main.py chat                       # 交互式对话（支持上下文记忆）
"""

import argparse
import logging
import os
import sys

from code_review_agent.agent import CodeReviewAgent
from code_review_agent.config import Config
from code_review_agent.memory import load_report, save_report

REVIEW_TASK_TEMPLATE = (
    "请审查以下目标：{target}。\n"
    "先查看项目结构，再仔细阅读代码，按约定的报告结构输出完整审查报告。"
)


def setup_logging(verbose: bool) -> None:
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")


def cmd_review(args) -> None:
    """一次性审查模式。"""
    config = Config()
    config.validate()

    target = os.path.abspath(args.target)
    if not os.path.exists(target):
        sys.exit(f"路径不存在: {target}")

    print(f"审查目标: {target}\n模型: {config.model}\n")
    # 审查根目录（文件审查时取文件所在目录），用于落盘历史报告
    review_dir = os.path.dirname(target) if os.path.isfile(target) else target
    agent = CodeReviewAgent(config, review_dir)

    rel = "." if os.path.abspath(target) == os.path.abspath(os.curdir) else target
    user_task = REVIEW_TASK_TEMPLATE.format(
        target=rel if os.path.isdir(target) else rel
    )
    if not os.path.isdir(target):
        # 单文件审查：root 设为文件所在目录，任务里指明文件名
        user_task = f"请审查当前目录下的文件 `{os.path.basename(target)}`。\n" \
                    "先阅读它，必要时检查它依赖的其他文件，按约定的报告结构输出完整审查报告。"

    print("Agent 思考中...")
    report = agent.run(user_task)

    print("\n" + "=" * 60 + "\n")
    print(report)

    # 落盘到审查目录，下次 chat 启动时自动加载作为背景
    save_report(review_dir, report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"\n报告已保存到: {args.output}")


def cmd_chat(args) -> None:
    """交互式对话模式，支持多轮上下文记忆。"""
    config = Config()
    config.validate()

    root = os.path.abspath(args.dir)
    print(f"代码审查助手（对话模式）\n工作目录: {root}")
    print("命令: /reset 清空记忆 | /exit 退出\n")
    # 如果本目录有上一次的审查报告，自动作为会话背景加载
    prior = load_report(root) or ""
    if prior:
        print(f"（已加载历史审查报告，可直接问「第 N 个问题」等追问）\n")
    agent = CodeReviewAgent(config, root, prior_context=prior)

    while True:
        try:
            user_input = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input:
            continue
        if user_input == "/exit":
            break
        if user_input == "/reset":
            agent.reset()
            print("（已清空对话记忆）\n")
            continue

        reply = agent.run(user_input)
        print(f"\nAgent>\n{reply}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="代码审查 Agent (Code Review Agent)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_review = sub.add_parser("review", help="一次性审查指定文件或目录")
    p_review.add_argument("target", help="要审查的文件或目录路径")
    p_review.add_argument("-o", "--output", help="将报告保存为 Markdown 文件")
    p_review.set_defaults(func=cmd_review)

    p_chat = sub.add_parser("chat", help="交互式对话（支持上下文记忆）")
    p_chat.add_argument("-d", "--dir", default=".", help="Agent 的工作目录")
    p_chat.set_defaults(func=cmd_chat)

    parser.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")
    args = parser.parse_args()
    setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
