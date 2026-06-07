"""路径安全校验工具

防止路径遍历攻击：所有用户输入的 ID 参数必须经过校验后才能用于文件路径。
"""
from __future__ import annotations

import re
from pathlib import Path


# 合法 ID 模式：字母/数字/下划线/连字符/点（不允许路径分隔符和遍历字符）
_SAFE_ID_PATTERN = re.compile(r'^[\w\-\.]+$')


def validate_id(name: str, value: str) -> str | None:
    """校验 ID 安全性，返回错误信息或 None（通过）

    Args:
        name: 参数名（用于错误信息）
        value: 待校验的值

    Returns:
        None 表示通过，str 表示错误信息
    """
    if not value or not value.strip():
        return f"{name} 不能为空"
    if not _SAFE_ID_PATTERN.match(value):
        return f"{name} '{value}' 包含非法字符（仅允许字母/数字/下划线/连字符/点）"
    if '..' in value:
        return f"{name} '{value}' 包含路径遍历字符 '..'"
    if value.startswith('.'):
        return f"{name} '{value}' 不能以点开头"
    return None


def safe_path(base: Path, *parts: str) -> Path | str:
    """构建安全路径，确保结果在 base 目录内

    Args:
        base: 基础目录（workspace）
        parts: 路径组件（用户输入的 ID）

    Returns:
        Path 表示安全路径，str 表示错误信息
    """
    resolved_base = base.resolve()
    result = resolved_base
    for part in parts:
        err = validate_id("path_component", part)
        if err:
            return err
        result = result / part
    resolved_result = result.resolve()
    if not resolved_result.is_relative_to(resolved_base):
        return f"路径越界: {resolved_result} 不在 {resolved_base} 内"
    return resolved_result
