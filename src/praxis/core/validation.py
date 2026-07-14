"""PRAXIS ID 校验工具

提供统一的 ID 格式校验，确保所有业务 ID 符合命名规范。
"""

from __future__ import annotations

import re

# 非法字符正则：不允许空格、控制字符、特殊符号
_INVALID_CHARS_PATTERN = re.compile(r'[\s\x00-\x1f<>:"/\\|?*]')

# 合法前缀列表
_VALID_PREFIXES: set[str] = {
    "tx",         # 交易 ID：tx-YYYYMMDD-NNN
    "dec",        # 决策 ID：dec-YYYYMMDD-NNN
    "inv",        # 投资者 ID：inv-{name}
    "port",       # 组合 ID：port-{name}
    "strat",      # 策略 ID
    "rule",       # 规则 ID
    "evt",        # 审计事件 ID
    "nav",        # 净值记录 ID
    "snap",       # 快照 ID
}


def validate_id(id_str: str, prefix: str) -> str:
    """校验 ID 格式

    规则：
    1. 必须以指定 prefix 开头（如 "tx-"、"dec-"）
    2. 不能为空
    3. 不能包含空格、控制字符、文件路径特殊字符
    4. 长度合理（3-128 字符）

    Args:
        id_str: 待校验的 ID 字符串
        prefix: 期望的前缀（不含末尾的连字符）

    Returns:
        校验通过的 ID 字符串（原样返回）

    Raises:
        ValueError: ID 格式不合法时抛出

    Example:
        >>> validate_id("tx-20250101-001", "tx")
        'tx-20250101-001'

        >>> validate_id("dec-20250101-005", "dec")
        'dec-20250101-005'

        >>> validate_id("bad-id", "tx")
        ValueError: ID "bad-id" 必须以 "tx-" 开头
    """
    if not id_str:
        raise ValueError("ID 不能为空")

    if not isinstance(id_str, str):
        raise ValueError(f"ID 必须是字符串，实际类型: {type(id_str).__name__}")

    # 长度检查
    if len(id_str) < 3:
        raise ValueError(f'ID "{id_str}" 长度不足（最少 3 字符）')
    if len(id_str) > 128:
        raise ValueError(f'ID "{id_str}" 长度超限（最多 128 字符）')

    # 前缀检查（需要包含连字符，如 "tx-"）
    expected_prefix = f"{prefix}-"
    if not id_str.startswith(expected_prefix):
        raise ValueError(
            f'ID "{id_str}" 必须以 "{expected_prefix}" 开头'
        )

    # 非法字符检查
    if _INVALID_CHARS_PATTERN.search(id_str):
        raise ValueError(
            f'ID "{id_str}" 包含非法字符（不允许空格、控制字符或文件路径特殊字符）'
        )

    # 前缀白名单检查（可选，宽松模式）
    clean_prefix = prefix.lower()
    if clean_prefix not in _VALID_PREFIXES:
        # 未知前缀，仅记录但不拒绝（允许自定义前缀）
        pass

    return id_str


def validate_ticker(ticker: str) -> str:
    """校验股票/ETF 代码格式

    支持的格式：
    - A 股：6 位数字（如 000001、600519）
    - ETF：6 位数字（如 510050、159915）
    - 港股：5 位数字（如 00700）
    - 海外基金：字母数字（如 VTI、SPY）

    Args:
        ticker: 标的代码

    Returns:
        校验通过的代码（去除首尾空格）

    Raises:
        ValueError: 代码格式不合法
    """
    if not ticker or not isinstance(ticker, str):
        raise ValueError(f"标的代码不能为空: {ticker}")

    ticker = ticker.strip().upper()

    if len(ticker) < 2:
        raise ValueError(f"标的代码长度不足: {ticker}")

    if len(ticker) > 20:
        raise ValueError(f"标的代码长度超限: {ticker}")

    if _INVALID_CHARS_PATTERN.search(ticker):
        raise ValueError(f"标的代码包含非法字符: {ticker}")

    return ticker


def is_valid_tx_id(tx_id: str) -> bool:
    """快速检查是否为合法交易 ID（不抛出异常）"""
    try:
        validate_id(tx_id, "tx")
        return True
    except ValueError:
        return False


def is_valid_decision_id(decision_id: str) -> bool:
    """快速检查是否为合法决策 ID（不抛出异常）"""
    try:
        validate_id(decision_id, "dec")
        return True
    except ValueError:
        return False
