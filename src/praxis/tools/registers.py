"""PRAXIS Tools — 统一注册导出

所有工具通过 register(registry) 导出，由 ToolRegistry.discover() 自动发现。
工具实现在各独立模块中，此文件仅做聚合注册。
"""
from __future__ import annotations

from praxis.agents.base import Tool, ToolRegistry

# 仅做聚合：每个工具模块的 register() 会被 discover() 自动调用
# 此处的 register 是备用手动注册入口

def register(registry: ToolRegistry):
    """手动注册所有的工具（备用入口）"""
    # 各工具模块的 register() 已通过 discover() 自动发现
    # 此函数为空，保留用于向后兼容
    pass
