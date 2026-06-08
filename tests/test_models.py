"""E1.1 — Pydantic Schema 验证测试"""
import pytest
from datetime import datetime, timezone
from praxis.core.models import (
    InvestorProfile, InvestorConstraints, ExecutionConfig,
    Portfolio, AssetEntry, SentinelEntry,
    AssetType, AssetCategory,
    StrategyTemplate, RuleEntry, AITeamConfig,
    Transaction, TransactionType, TransactionStatus,
    DecisionRecord, DecisionStatus, TeamSignal,
    PortfolioState, PositionState, CashState,
    AuditEvent, AuditEventType,
    PraxisError, ConfigError, DataError, ReconcileError,
)


class TestAssetEnums:
    """测试资产枚举"""

    def test_asset_type_values(self):
        assert AssetType.STOCK == "stock"
        assert AssetType.ETF == "etf"
        assert AssetType.OFFSHORE_FUND == "offshore_fund"

    def test_asset_category_values(self):
        assert AssetCategory.POWER_INFRA == "power_infra"
        assert AssetCategory.TECH_SATELLITE == "tech_satellite"
        assert AssetCategory.DEFENSIVE_BASE == "defensive_base"
        assert AssetCategory.SCIENCE_BOARD == "science_board"


class TestInvestorProfile:
    """测试投资者画像模型"""

    def test_minimal_profile(self):
        profile = InvestorProfile(
            name="测试投资者",
            id="test",
            capital_cny=100000,
            risk_level="C3",
            style="balanced",
        )
        assert profile.name == "测试投资者"
        assert profile.capital_cny == 100000

    def test_full_profile(self):
        profile = InvestorProfile(
            name="示例投资者",
            id="example",
            capital_cny=70000,
            risk_level="C3-C4",
            style="balanced_growth",
            max_drawdown_pct=20,
            constraints=InvestorConstraints(
                banned_markets=[{"id": "star_market", "desc": "科创板"}],
                banned_instruments=["leverage", "options"],
                etf_exemption=True,
            ),
            execution=ExecutionConfig(
                offshore_fund_window="14:45-14:55",
                min_transaction_cny=3000,
            ),
        )
        assert profile.constraints.etf_exemption is True
        assert profile.execution.min_transaction_cny == 3000


class TestPortfolio:
    """测试投资组合模型"""

    def test_portfolio_with_assets(self):
        portfolio = Portfolio(
            strategy_type="grid_value",
            strategy_template="grid_value",
            created_at="2026-05-18",
            version="v9.0",
            assets=[
                AssetEntry(
                    ticker="600995",
                    name="南网储能",
                    type=AssetType.STOCK,
                    category=AssetCategory.POWER_INFRA,
                    target_weight_pct=12,
                ),
            ],
        )
        assert len(portfolio.assets) == 1
        assert portfolio.assets[0].ticker == "600995"


class TestTransaction:
    """测试交易记录模型"""

    def test_buy_transaction(self):
        tx = Transaction(
            tx_id="tx-20260601-001",
            type=TransactionType.BUY,
            ticker="600995",
            quantity=100,
            price=13.50,
            fee=5.0,
        )
        assert tx.type == TransactionType.BUY
        assert tx.status == TransactionStatus.CONFIRMED

    def test_transaction_to_jsonl(self):
        tx = Transaction(
            tx_id="tx-20260601-001",
            type=TransactionType.BUY,
            ticker="600995",
            quantity=100,
            price=13.50,
        )
        jsonl = tx.to_jsonl()
        assert '"tx_id": "tx-20260601-001"' in jsonl
        assert '"type": "buy"' in jsonl

    def test_transaction_types(self):
        assert TransactionType.BUY == "buy"
        assert TransactionType.SELL == "sell"
        assert TransactionType.SUBSCRIBE == "subscribe"
        assert TransactionType.REDEEM == "redeem"
        assert TransactionType.DIVIDEND == "dividend"
        assert TransactionType.CORRECTION == "correction"


class TestDecisionRecord:
    """测试决策记录模型"""

    def test_decision_record(self):
        record = DecisionRecord(
            decision_id="dc-20260601-001",
            ticker="600995",
            action="buy",
            confidence=0.75,
            reasoning="网格触发",
        )
        assert record.status == DecisionStatus.PENDING_APPROVAL
        assert record.confidence == 0.75

    def test_team_signal(self):
        signal = TeamSignal(
            recommendation="buy",
            confidence=0.72,
            evidence=["MA20多头"],
        )
        assert signal.recommendation == "buy"
        assert len(signal.evidence) == 1


class TestAuditEvent:
    """测试审计事件模型"""

    def test_audit_event(self):
        event = AuditEvent(
            event_id="evt-20260601-001",
            event_type=AuditEventType.TOOL_CALL,
            tool_name="get_portfolio",
        )
        assert event.success is True
        assert event.event_type == AuditEventType.TOOL_CALL


class TestErrorModels:
    """测试错误模型"""

    def test_praxis_error(self):
        error = PraxisError("测试错误", code="TEST_ERROR")
        assert error.message == "测试错误"
        assert error.code == "TEST_ERROR"
        assert error.to_dict()["error"] == "TEST_ERROR"

    def test_config_error(self):
        error = ConfigError("配置不存在", path="/test/path")
        assert error.code == "CONFIG_ERROR"
        assert error.details["path"] == "/test/path"

    def test_data_error(self):
        error = DataError("API 超时", source="tencent")
        assert error.code == "DATA_ERROR"
        assert error.details["source"] == "tencent"

    def test_reconcile_error(self):
        error = ReconcileError("对账失败")
        assert error.code == "RECONCILE_ERROR"
