"""PRAXIS 项目级共享 fixtures.

为 Core / Engine / Agents / Tools 各层的测试提供可复用的
样本数据 fixtures。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from praxis.core.models import (
    AssetCategory,
    AssetEntry,
    AssetType,
    InvestorConstraints,
    InvestorProfile,
    Portfolio,
    RuleEntry,
    SentinelEntry,
    StrategyTemplate,
    Transaction,
    TransactionType,
)


@pytest.fixture
def tmp_workspace() -> Path:
    """创建临时工作空间目录，含基本 config/data 子目录结构。

    作用域: function
    Yields:
        Path: 临时目录路径
    """
    with tempfile.TemporaryDirectory(prefix="praxis_test_") as tmpdir:
        root = Path(tmpdir)
        (root / "config").mkdir()
        (root / "data").mkdir()
        (root / "ledger").mkdir()
        yield root


@pytest.fixture(scope="module")
def sample_investor() -> InvestorProfile:
    """默认投资者画像。

    作用域: module
    Returns:
        InvestorProfile: capital=100000, risk_level=C3 的默认画像
    """
    return InvestorProfile(
        investor_id="inv-test-default",
        name="测试投资者",
        capital_cny=100_000.0,
        risk_level="C3",
        style="balanced",
        max_drawdown_pct=20.0,
        constraints=InvestorConstraints(),
        execution=InvestorConstraints.__init__.__defaults__,
    )


@pytest.fixture(scope="module")
def sample_portfolio() -> Portfolio:
    """默认投资组合，含 4 个 AssetEntry。

    作用域: module
    Returns:
        Portfolio: 含 000001/600519/159915/510050 四个资产的组合
    """
    assets = [
        AssetEntry(
            ticker="000001",
            name="平安银行",
            asset_type=AssetType.STOCK,
            category=AssetCategory.LARGE_CAP,
            target_weight_pct=20.0,
        ),
        AssetEntry(
            ticker="600519",
            name="贵州茅台",
            asset_type=AssetType.STOCK,
            category=AssetCategory.LARGE_CAP,
            target_weight_pct=25.0,
        ),
        AssetEntry(
            ticker="159915",
            name="创业板ETF",
            asset_type=AssetType.ETF,
            category=AssetCategory.BROAD_MARKET,
            target_weight_pct=15.0,
        ),
        AssetEntry(
            ticker="510050",
            name="50ETF",
            asset_type=AssetType.ETF,
            category=AssetCategory.BROAD_MARKET,
            target_weight_pct=10.0,
        ),
    ]
    return Portfolio(
        portfolio_id="port-test-default",
        investor_id="inv-test-default",
        name="测试组合",
        strategy_type="grid_value",
        benchmark="000300",
        assets=assets,
        sentinels=[],
    )


@pytest.fixture(scope="module")
def sample_strategy() -> StrategyTemplate:
    """含 5 条 RuleEntry 的 grid_value 策略模板。

    作用域: module
    Returns:
        StrategyTemplate: grid_value 策略模板
    """
    rules = [
        RuleEntry(
            rule_id="risk.cash_floor",
            name="现金底线",
            description="交易后现金不低于总资产的5%",
            level="hard_block",
            enabled=True,
            params={"min_pct": 5.0},
        ),
        RuleEntry(
            rule_id="position.single_cap",
            name="单标的上限",
            description="单一标的持仓不超过总资产的30%",
            level="hard_block",
            enabled=True,
            params={"max_pct": 30.0},
        ),
        RuleEntry(
            rule_id="risk.stop_loss",
            name="止损线",
            description="单笔亏损超10%必须止损",
            level="hard_block",
            enabled=True,
            params={"max_loss_pct": 10.0},
        ),
        RuleEntry(
            rule_id="risk.daily_trade_limit",
            name="日交易上限",
            description="每日最多5笔交易",
            level="soft_warning",
            enabled=True,
            params={"max_trades": 5},
        ),
        RuleEntry(
            rule_id="process.review_5d",
            name="5日复盘",
            description="交易后5日必须完成复盘",
            level="soft_warning",
            enabled=True,
        ),
    ]
    return StrategyTemplate(
        strategy_name="grid_value",
        version="1.0.0",
        description="网格价值策略 — 测试模板",
        rules=rules,
    )


@pytest.fixture
def sample_transaction_buy() -> Transaction:
    """单笔买入交易：000001, BUY, 100@10。

    作用域: function
    Returns:
        Transaction: 买入 000001 的 PENDING 交易
    """
    return Transaction(
        ticker="000001",
        tx_type=TransactionType.BUY,
        quantity=100.0,
        price=10.0,
        fee=1.5,
        asset_type=AssetType.STOCK,
        investor_id="inv-test-default",
        portfolio_id="port-test-default",
        tags=["test"],
    )
