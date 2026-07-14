"""PRAXIS Feature Flag 系统

支持六大开关，安全灰度发布。
所有 flag 默认为旧行为（安全优先：默认关闭新功能）。

Usage:
    from praxis.core.feature_flags import FeatureFlag

    if FeatureFlag.is_enabled("PRAXIS_AGENT_MODE"):
        # 使用 Agent 模式
    else:
        # 使用旧版 mcp_server_legacy 模式
"""

from __future__ import annotations

import os


# 六大开关定义（类级别常量，不在 dataclass __init__ 中）
_FLAG_DEFINITIONS: dict = {
    "PRAXIS_AGENT_MODE": {
        "default": True,
        "description": "Agent 模式：True=使用 Agent 架构，False=旧版上帝文件",
    },
    "PRAXIS_GUARDRAIL_ENABLED": {
        "default": True,
        "description": "Guardrail 纪律锁：True=开启写操作前置拦截",
    },
    "PRAXIS_STORAGE_BACKEND": {
        "default": "jsonl",
        "description": "存储后端：jsonl=JSONL文件(当前)，sqlite=SQLite数据库(P3后)",
    },
    "PRAXIS_MEMORY_ENABLED": {
        "default": False,
        "description": "长期记忆：True=启用向量库记忆，False=禁用",
    },
    "PRAXIS_ORCHESTRATION_MODE": {
        "default": "agent",
        "description": "编排模式：agent=Agent编排，direct=直接调用，hybrid=混合",
    },
    "PRAXIS_AUTO_SESSION": {
        "default": True,
        "description": (
            "自动会话管理：True=T+1非交易时段自动LOCKED，"
            "False=手动管理Guardrail状态"
        ),
    },
}


class FeatureFlag:
    """特性开关管理器（全静态方法，无需实例化）"""

    @classmethod
    def is_enabled(cls, flag_name: str) -> bool:
        """查询布尔型开关

        Returns:
            环境变量值（fallback 到默认值）
        """
        flag_def = _FLAG_DEFINITIONS.get(flag_name)
        if flag_def is None:
            return False
        default = flag_def["default"]
        env_value = os.environ.get(flag_name)
        if env_value is None:
            return default if isinstance(default, bool) else False
        return env_value.lower() in ("true", "1", "yes", "on")

    @classmethod
    def get_value(cls, flag_name: str) -> str | bool:
        """查询任意类型开关值

        Returns:
            环境变量值（fallback 到默认值）
        """
        flag_def = _FLAG_DEFINITIONS.get(flag_name)
        if flag_def is None:
            return False
        default = flag_def["default"]
        return os.environ.get(flag_name, str(default))

    @classmethod
    def list_all(cls) -> dict:
        """列出所有开关及其当前值"""
        return {
            name: {
                "value": cls.get_value(name),
                "description": _FLAG_DEFINITIONS[name]["description"],
                "default": _FLAG_DEFINITIONS[name]["default"],
            }
            for name in _FLAG_DEFINITIONS
        }

    @classmethod
    def get_storage_backend(cls) -> str:
        """获取当前存储后端"""
        return str(cls.get_value("PRAXIS_STORAGE_BACKEND"))

    @classmethod
    def is_auto_session_enabled(cls) -> bool:
        """查询 PRAXIS_AUTO_SESSION 开关

        True: T+1 非交易时段自动将 Guardrail 切换为 LOCKED
        False: 手动管理 Guardrail 状态
        """
        return cls.is_enabled("PRAXIS_AUTO_SESSION")
