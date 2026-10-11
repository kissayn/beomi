"""工具集：Agent 可调用的能力。

安全设计：所有文件操作都被限制在「审查目标目录」内，
不允许读取目标目录之外的文件（防止 Prompt 注入诱导越权读取）。
"""

import fnmatch
import logging
import os
import py_compile
import re
import tempfile

logger = logging.getLogger(__name__)

# 审查时跳过的目录（虚拟环境、版本控制、缓存等）
IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".idea", ".vscode"}
# 只审查这些类型的代码文件
CODE_EXTS = {".py", ".js", ".ts", ".java", ".go", ".c", ".h", ".cpp", ".hpp", ".rs", ".rb"}


class Tools:
    """工具注册中心：定义工具的 JSON Schema 并负责执行。"""

    def __init__(self, root: str, output_limit: int = 15000):
        self.root = os.path.abspath(root)
        self.output_limit = output_limit

    # ---------- 安全检查 ----------

    def _safe_path(self, path: str) -> str:
        """把相对路径解析到 root 内，越界则抛异常。"""
        abs_path = os.path.abspath(os.path.join(self.root, path))
        if not (abs_path == self.root or abs_path.startswith(self.root + os.sep)):
            raise PermissionError(f"禁止访问审查目录之外的路径: {path}")
        return abs_path

    def _truncate(self, text: str) -> str:
        if len(text) > self.output_limit:
            return text[: self.output_limit] + f"\n...[结果过长，已截断，共 {len(text)} 字符]"
        return text

    # ---------- 工具实现 ----------

    def read_file(self, path: str) -> str:
        """读取指定代码文件的内容。"""
        abs_path = self._safe_path(path)
        if not os.path.isfile(abs_path):
            return f"错误：文件不存在: {path}"
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            return self._truncate(f.read())

    def list_files(self, path: str = ".") -> str:
        """列出目录下的代码文件树（自动跳过 .git/venv 等无关目录）。"""
        abs_path = self._safe_path(path)
        if not os.path.isdir(abs_path):
            return f"错误：目录不存在: {path}"

        lines = []
        base_depth = abs_path.count(os.sep)
        for dirpath, dirnames, filenames in os.walk(abs_path):
            dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
            rel_dir = os.path.relpath(dirpath, abs_path)
            depth = dirpath.count(os.sep) - base_depth
            indent = "  " * depth
            if rel_dir != ".":
                lines.append(f"{indent}{os.path.basename(rel_dir)}/")
            for name in sorted(filenames):
                if name.endswith((".md", ".txt", ".toml", ".cfg", ".ini")) or any(
                    name.endswith(e) for e in CODE_EXTS
                ):
                    size = os.path.getsize(os.path.join(dirpath, name))
                    lines.append(f"{indent}  {name} ({size}B)")
            if len(lines) > 200:
                lines.append("...[文件过多，已截断]")
                break
        return "\n".join(lines) or "（目录为空）"

    def search_code(self, pattern: str, path: str = ".") -> str:
        """在代码文件中搜索文本（不支持正则，纯子串匹配），返回 文件:行号:内容。"""
        abs_path = self._safe_path(path)
        matches = []
        try:
            compiled = re.compile(pattern)
            is_regex = True
        except re.error:
            is_regex = False

        for dirpath, dirnames, filenames in os.walk(abs_path):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            for name in filenames:
                if not any(name.endswith(e) for e in CODE_EXTS):
                    continue
                file_path = os.path.join(dirpath, name)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for lineno, line in enumerate(f, 1):
                            hit = compiled.search(line) if is_regex else (pattern in line)
                            if hit:
                                rel = os.path.relpath(file_path, self.root)
                                matches.append(f"{rel}:{lineno}: {line.rstrip()}")
                                if len(matches) >= 100:
                                    matches.append("...[超过100条，已截断]")
                                    return "\n".join(matches)
                except OSError:
                    continue
        return "\n".join(matches) if matches else "未找到匹配内容"

    def check_syntax(self, path: str) -> str:
        """对 Python 文件做语法检查（py_compile），返回错误信息或通过。"""
        abs_path = self._safe_path(path)
        if not os.path.isfile(abs_path) or not abs_path.endswith(".py"):
            return "错误：check_syntax 仅支持 .py 文件"
        # 写入临时 pyc，避免污染目标项目的 __pycache__
        with tempfile.TemporaryDirectory() as tmp:
            try:
                py_compile.compile(abs_path, cfile=os.path.join(tmp, "out.pyc"))
                return "语法检查通过"
            except py_compile.PyCompileError as e:
                return f"语法错误：\n{e}"

    # ---------- OpenAI Function Calling Schema ----------

    @property
    def schemas(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "读取指定代码文件的内容。优先用它了解代码，再给出审查意见。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "相对审查目录的文件路径"}
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "列出目录下的代码文件树，用于了解项目结构。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "相对审查目录的目录路径，默认 '.'"}
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "在项目中搜索文本或正则表达式，返回 文件:行号:内容。适合定位某个函数/变量的所有用法。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string", "description": "要搜索的文本或正则表达式"},
                            "path": {"type": "string", "description": "限定搜索的目录，默认 '.'"},
                        },
                        "required": ["pattern"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "check_syntax",
                    "description": "对某个 Python 文件做语法检查，快速发现语法错误。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "相对审查目录的 .py 文件路径"}
                        },
                        "required": ["path"],
                    },
                },
            },
        ]

    def execute(self, name: str, arguments: dict) -> str:
        """按名称分发执行工具，任何异常都转为错误文本（不中断 Agent 循环）。"""
        dispatch = {
            "read_file": self.read_file,
            "list_files": self.list_files,
            "search_code": self.search_code,
            "check_syntax": self.check_syntax,
        }
        func = dispatch.get(name)
        if func is None:
            return f"错误：未知工具 {name}"
        try:
            return func(**arguments)
        except PermissionError as e:
            return f"错误：{e}"
        except TypeError as e:
            return f"错误：参数不合法 {e}"
        except Exception as e:  # noqa: BLE001
            logger.exception("工具 %s 执行失败", name)
            return f"错误：工具执行失败 {type(e).__name__}: {e}"
