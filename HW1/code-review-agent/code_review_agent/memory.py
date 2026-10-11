"""跨进程持久化记忆：把上一次审查报告落盘，下次会话启动时自动加载。"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 持久化文件名（隐藏文件，不会污染项目）
REPORT_FILE = ".code_review_last_report.md"


def save_report(target_dir: str, report: str) -> None:
    """把审查报告保存到目标目录，供下次会话作为上下文加载。"""
    abs_dir = os.path.abspath(target_dir)
    path = os.path.join(abs_dir, REPORT_FILE)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        logger.debug("审查报告已持久化到 %s", path)
    except OSError as e:
        # 持久化失败不影响本次审查
        logger.warning("持久化审查报告失败: %s", e)


def load_report(target_dir: str) -> Optional[str]:
    """加载目录里上一次保存的审查报告；不存在则返回 None。"""
    path = os.path.join(os.path.abspath(target_dir), REPORT_FILE)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        logger.warning("读取历史审查报告失败: %s", e)
        return None