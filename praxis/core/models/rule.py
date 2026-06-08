"""规则 Schema 定义

GPT 要求：每个规则都要有参数 Schema、版本管理。
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class RuleLevel(str, Enum):
    """规则级别"""
    HARD_INVARIANT = "hard_invariant"    # 绝对不能破坏
    HARD_BLOCK = "hard_block"            # 触发后禁止执行
    SOFT_WARNING = "soft_warning"        # 触发后提醒
    ADVISORY = "advisory"                # 仅作为建议
    STRATEGY_SPECIFIC = "strategy_specific"  # 策略专属
    INVESTOR_SPECIFIC = "investor_specific"  # 投资者个性


class RuleDefinition(BaseModel):
    """规则定义"""
    rule_id: str
    name: str
    description: str
    level: RuleLevel
    version: str = "1.0.0"
    default_enabled: bool = True
    can_disable: bool = False
    requires: list[str] = Field(default_factory=list)  # 依赖的状态字段
    params: dict = Field(default_factory=dict)          # 参数 Schema
    test_cases: list[dict] = Field(default_factory=list)  # 测试用例


# 预定义规则
PREDEFINED_RULES = {
    "risk.cash_floor": RuleDefinition(
        rule_id="risk.cash_floor",
        name="现金底线",
        description="现金比例不能低于指定阈值",
        level=RuleLevel.HARD_BLOCK,
        requires=["state.available_cash_cny", "state.total_assets_cny"],
        params={"min_cash_ratio": 0.40},
        test_cases=[
            {
                "name": "现金充足应通过",
                "input": {"available_cash_ratio": 0.50, "action": "buy"},
                "expected": "pass",
            },
            {
                "name": "现金不足应阻止",
                "input": {"available_cash_ratio": 0.30, "action": "buy"},
                "expected": "block",
            },
        ],
    ),
    "risk.position_cap": RuleDefinition(
        rule_id="risk.position_cap",
        name="单标的持仓上限",
        description="单个标的持仓不能超过总资产的指定比例",
        level=RuleLevel.HARD_BLOCK,
        requires=["state.position_value", "state.total_assets_cny"],
        params={"max_single_pct": 0.15},
        test_cases=[
            {
                "name": "持仓比例正常应通过",
                "input": {"position_ratio": 0.10, "action": "buy"},
                "expected": "pass",
            },
            {
                "name": "持仓比例过高应阻止",
                "input": {"position_ratio": 0.20, "action": "buy"},
                "expected": "block",
            },
        ],
    ),
    "access.banned_market": RuleDefinition(
        rule_id="access.banned_market",
        name="禁入板块",
        description="禁止投资特定板块（科创板/创业板）",
        level=RuleLevel.HARD_INVARIANT,
        can_disable=False,
        params={"banned_markets": ["star_market", "chinext"], "etf_exempt": True},
        test_cases=[
            {
                "name": "科创板股票应阻止",
                "input": {"ticker": "688001", "is_etf": False},
                "expected": "block",
            },
            {
                "name": "科创板ETF应通过",
                "input": {"ticker": "ETF_500", "is_etf": True},
                "expected": "pass",
            },
        ],
    ),
    "execution.min_transaction": RuleDefinition(
        rule_id="execution.min_transaction",
        name="最小交易金额",
        description="单笔交易金额不能低于指定阈值",
        level=RuleLevel.HARD_BLOCK,
        params={"min_amount_cny": 3000},
        test_cases=[
            {
                "name": "金额充足应通过",
                "input": {"amount": 5000, "action": "buy"},
                "expected": "pass",
            },
            {
                "name": "金额不足应阻止",
                "input": {"amount": 2000, "action": "buy"},
                "expected": "block",
            },
        ],
    ),
    "access.banned_instrument": RuleDefinition(
        rule_id="access.banned_instrument",
        name="禁入工具",
        description="禁止使用特定金融工具（杠杆/期权/做空）",
        level=RuleLevel.HARD_INVARIANT,
        can_disable=False,
        params={"banned_instruments": ["leverage", "options", "short"]},
        test_cases=[
            {
                "name": "普通股票应通过",
                "input": {"instrument": "stock"},
                "expected": "pass",
            },
        ],
    ),
}
