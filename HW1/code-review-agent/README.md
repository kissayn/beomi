# Code Review Agent · 代码审查智能体

一个基于 LLM 的命令行代码审查助手：给定一个文件或项目目录，它会自主浏览代码、
查找潜在 Bug、代码质量问题和安全风险，并输出结构化的中文审查报告。

## 特性

- **完整 Agent 循环**：输入 → 推理 → 工具调用 → 输出，循环直到得出结论
- **4 个内置工具**：列出文件树 / 读取文件 / 全局代码搜索 / Python 语法检查
- **上下文记忆**：对话模式下多轮共享记忆，工具调用结果也进入上下文
- **健壮性**：API 指数退避重试、工具异常不中断循环、最大轮数防失控、目录越权防护
- **LLM 可配置**：默认 DeepSeek，兼容任何 OpenAI 协议服务商

## 快速开始

```bash
# 1. 安装依赖（建议 Python 3.10+）
pip install -r requirements.txt

# 2. 配置 API Key（申请地址 https://platform.deepseek.com/）
copy .env.example .env
#    编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 一键审查（目录或单个文件均可）
python main.py review examples
python main.py review examples/bad_example.py -o report.md

# 4. 交互对话模式
python main.py chat -d examples
```

## 使用示例

```
> python main.py review examples/bad_example.py
审查目标: c:\...\examples\bad_example.py
模型: deepseek-chat

Agent 思考中...
  [工具] read_file({"path": "bad_example.py"})
  [结果] """演示用：这是一份故意写了很多问题的代码，用来测试代码审查 A
  ...

============================================================

## 总体评价
该文件实现了一个用户管理模块，功能可用但存在多处严重问题...

## 问题清单
🔴 严重
- examples/bad_example.py:43 `os.system("rm -rf ./data")`
  危险的 shell 调用 + 删除操作无确认 ...
...
```

对话模式：

```
> python main.py chat -d examples
你> 帮我看看这个项目的代码质量
Agent> ...
你> 刚才提到的第 3 个问题具体怎么改？
Agent> （基于上下文记忆继续回答）
你> /reset        # 清空记忆
你> /exit         # 退出
```

## 项目结构

```
code-review-agent/
├── main.py                     # CLI 入口（review / chat 两种模式）
├── code_review_agent/
│   ├── config.py               # 配置（环境变量 / .env）
│   ├── llm.py                  # LLM 客户端 + 指数退避重试
│   ├── tools.py                # 4 个工具的实现与 Schema
│   └── agent.py                # Agent 核心循环 + 上下文记忆
├── examples/bad_example.py     # 演示用的"问题代码"
├── Design.md                   # 设计文档（架构图、决策说明）
├── requirements.txt
└── .env.example
```

## 配置项（.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key（必填） | - |
| `CODE_REVIEW_MODEL` | 模型名 | `deepseek-chat` |
| `LLM_BASE_URL` | OpenAI 兼容接口地址 | `https://api.deepseek.com` |

## 常见问题

- **提示未配置 Key**：把 `.env.example` 复制为 `.env` 并填入 Key。
- **想换服务商**：设置 `LLM_BASE_URL` 与 `CODE_REVIEW_MODEL` 即可（如通义千问兼容模式）。
- **报告太长被截断**：缩小审查范围（审查单个文件），或分目录多次审查。
