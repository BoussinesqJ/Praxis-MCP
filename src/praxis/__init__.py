"""PRAXIS Agent - AI驱动的投研纪律系统

基于 Agent 架构重构的 PRAXIS 核心模块。
将 1272 行的 mcp_server.py 上帝文件拆分为 5 个独立 Agent + 轻量编排器。

Architecture:
    src/praxis/
    ├── agents/         # Agent 抽象框架 + 5 个 Agent 实现
    ├── core/           # 核心接口、数据模型、Guardrail、日志、FeatureFlag
    ├── tools/          # 28 个 MCP 工具实现 + Pydantic Schema
    ├── db/             # SQLite Schema + 数据库初始化
    ├── engine/         # 数据提供器引擎
    └── mcp_server.py   # 瘦身编排器 (≤250行)
"""

__version__ = "5.0.0"

# Feature Flag 系统 — 安全默认值：默认关闭新功能
import os

FEATURE_FLAGS = {
    "PRAXIS_AGENT_MODE": os.environ.get("PRAXIS_AGENT_MODE", "true").lower() == "true",
    "PRAXIS_GUARDRAIL_ENABLED": os.environ.get("PRAXIS_GUARDRAIL_ENABLED", "true").lower() == "true",
    "PRAXIS_STORAGE_BACKEND": os.environ.get("PRAXIS_STORAGE_BACKEND", "jsonl"),
    "PRAXIS_MEMORY_ENABLED": os.environ.get("PRAXIS_MEMORY_ENABLED", "false").lower() == "true",
    "PRAXIS_ORCHESTRATION_MODE": os.environ.get("PRAXIS_ORCHESTRATION_MODE", "agent"),
}


def is_feature_enabled(feature_name: str) -> bool:
    """查询 Feature Flag 状态"""
    return FEATURE_FLAGS.get(feature_name, False)
