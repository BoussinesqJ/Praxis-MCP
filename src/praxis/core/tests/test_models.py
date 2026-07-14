"""tests for core/models.py — 6 Enum + 26 Pydantic BaseModel."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from praxis.core.models import (
    # Enums
    AssetType,
    AssetCategory,
    TransactionType,
    TransactionStatus,
    DecisionStatus,
    AuditEventType,
    # 投资者模型
    InvestorProfile,
    InvestorConstraints,
    ExecutionConfig,
    # 组合模型
    Portfolio,
    AssetEntry,
    SentinelEntry,
    # 策略模型
    StrategyTemplate,
    RuleEntry,
    # 交易与决策
    Transaction,
    DecisionRecord,
    TeamSignal,
    # 状态模型
    PortfolioState,
    CashState,
    PositionState,
    # 审计
    AuditEvent,
    # 哨兵
    SentinelSignal,
    SentinelSnapshot,
    # 估值
    ValuationPercentile,
    # 绩效
    PerformanceMetrics,
    # 复盘
    ReviewSnapshot,
    ReviewPeriod,
    MarketDimension,
    PortfolioDimension,
    SentinelDimension,
    PerformanceDimension,
    DecisionReviewDimension,
    ValuationDimension,
    CascadeDimension,
    SingleDecisionReview,
)


# ── 场景1：Enum 值校验 ──────────────────────────────────────────


class TestEnumValues:
    """验证所有 Enum 的 .value 属性与成员一致。"""

    def test_asset_type_values(self):
        """AssetType 5 个值：stock/etf/offshore_fund/bond/cash。"""
        assert AssetType.STOCK.value == "stock"
        assert AssetType.ETF.value == "etf"
        assert AssetType.OFFSHORE_FUND.value == "offshore_fund"
        assert AssetType.BOND.value == "bond"
        assert AssetType.CASH.value == "cash"
        assert len(AssetType) == 5

    def test_asset_category_values(self):
        """AssetCategory 9 个值。"""
        assert AssetCategory.LARGE_CAP.value == "large_cap"
        assert AssetCategory.SMALL_CAP.value == "small_cap"
        assert AssetCategory.GROWTH.value == "growth"
        assert AssetCategory.VALUE.value == "value"
        assert AssetCategory.DEFENSIVE.value == "defensive"
        assert AssetCategory.CYCLICAL.value == "cyclical"
        assert AssetCategory.BROAD_MARKET.value == "broad_market"
        assert AssetCategory.SECTOR.value == "sector"
        assert AssetCategory.BOND.value == "bond"
        assert len(AssetCategory) == 9

    def test_transaction_type_values(self):
        """TransactionType 6 个值。"""
        assert TransactionType.BUY.value == "buy"
        assert TransactionType.SELL.value == "sell"
        assert TransactionType.SUBSCRIBE.value == "subscribe"
        assert TransactionType.REDEEM.value == "redeem"
        assert TransactionType.DIVIDEND.value == "dividend"
        assert TransactionType.REVERSE.value == "reverse"
        assert len(TransactionType) == 6

    def test_transaction_status_values(self):
        """TransactionStatus 5 个值。"""
        assert TransactionStatus.PENDING.value == "pending"
        assert TransactionStatus.APPROVED.value == "approved"
        assert TransactionStatus.REJECTED.value == "rejected"
        assert TransactionStatus.EXECUTED.value == "executed"
        assert TransactionStatus.REVERSED.value == "reversed"
        assert len(TransactionStatus) == 5

    def test_decision_status_values(self):
        """DecisionStatus 7 个值。"""
        assert DecisionStatus.DRAFT.value == "draft"
        assert DecisionStatus.PENDING.value == "pending"
        assert DecisionStatus.APPROVED.value == "approved"
        assert DecisionStatus.REJECTED.value == "rejected"
        assert DecisionStatus.EXECUTED.value == "executed"
        assert DecisionStatus.REVIEWED.value == "reviewed"
        assert DecisionStatus.EXPIRED.value == "expired"
        assert len(DecisionStatus) == 7

    def test_audit_event_type_values(self):
        """AuditEventType 7 个值。"""
        assert AuditEventType.TRADE.value == "trade"
        assert AuditEventType.DECISION.value == "decision"
        assert AuditEventType.CONSTRAINT.value == "constraint"
        assert AuditEventType.STATE_CHANGE.value == "state_change"
        assert AuditEventType.CONFIG_CHANGE.value == "config_change"
        assert AuditEventType.ERROR.value == "error"
        assert AuditEventType.GUARDRAIL.value == "guardrail"
        assert len(AuditEventType) == 7


# ── 场景2：InvestorProfile + InvestorConstraints + ExecutionConfig 嵌套构造 ──


class TestInvestorProfileNested:
    """嵌套构造 invest_profile + constraints + execution。"""

    def test_minimal_construction(self):
        """capital_cny 必填 >0, risk_level 默认 C3。"""
        profile = InvestorProfile(
            investor_id="inv-test",
            name="测试",
            capital_cny=50000.0,
        )
        assert profile.capital_cny == 50000.0
        assert profile.risk_level == "C3"
        assert profile.style == "balanced"
        # 默认工厂
        assert isinstance(profile.constraints, InvestorConstraints)
        assert isinstance(profile.execution, ExecutionConfig)

    def test_capital_cny_must_be_positive(self):
        """capital_cny >0 约束：0 或负数抛出 ValidationError。"""
        with pytest.raises(ValidationError):
            InvestorProfile(
                investor_id="inv-test",
                name="测试",
                capital_cny=0,
            )
        with pytest.raises(ValidationError):
            InvestorProfile(
                investor_id="inv-test",
                name="测试",
                capital_cny=-100,
            )

    def test_risk_level_pattern(self):
        """risk_level 满足 ^C[1-5]$ 正则。"""
        # 合法值
        for level in ["C1", "C2", "C3", "C4", "C5"]:
            profile = InvestorProfile(
                investor_id="inv-test", name="测试", capital_cny=10000,
                risk_level=level,
            )
            assert profile.risk_level == level

    def test_risk_level_invalid_pattern(self):
        """risk_level 不符合 C1-C5 正则抛出 ValidationError。"""
        for bad in ["C0", "C6", "D3", "c3", "C10", "ABC"]:
            with pytest.raises(ValidationError):
                InvestorProfile(
                    investor_id="inv-test", name="测试", capital_cny=10000,
                    risk_level=bad,
                )

    def test_constraints_default_factory(self):
        """constraints 子对象默认工厂自动创建，max_single_position_pct 默认 30。"""
        profile = InvestorProfile(
            investor_id="inv-test", name="测试", capital_cny=10000,
        )
        assert profile.constraints.max_single_position_pct == 30.0
        assert profile.constraints.max_sector_exposure_pct == 50.0
        assert profile.constraints.min_cash_reserve_pct == 5.0
        assert profile.constraints.max_daily_trades == 5

    def test_constraints_boundary(self):
        """max_single_position_pct ge=0, le=100 边界校验。"""
        # 合法边界
        c = InvestorConstraints(max_single_position_pct=0)
        assert c.max_single_position_pct == 0
        c = InvestorConstraints(max_single_position_pct=100)
        assert c.max_single_position_pct == 100

        # 非法
        with pytest.raises(ValidationError):
            InvestorConstraints(max_single_position_pct=-1)
        with pytest.raises(ValidationError):
            InvestorConstraints(max_single_position_pct=101)

    def test_execution_defaults(self):
        """ExecutionConfig 默认值：fee_rate 0.03, slippage 5, stop_loss enabled。"""
        profile = InvestorProfile(
            investor_id="inv-test", name="测试", capital_cny=10000,
        )
        assert profile.execution.default_fee_rate_pct == 0.03
        assert profile.execution.slippage_bps == 5.0
        assert profile.execution.enable_stop_loss is True
        assert profile.execution.stop_loss_pct == 10.0

    def test_full_nested_construction(self):
        """完整嵌套构造：所有字段自定义。"""
        constraints = InvestorConstraints(
            max_single_position_pct=25.0,
            max_sector_exposure_pct=40.0,
            min_cash_reserve_pct=10.0,
            max_daily_trades=3,
        )
        execution = ExecutionConfig(
            default_fee_rate_pct=0.05,
            slippage_bps=3.0,
            enable_stop_loss=False,
            stop_loss_pct=15.0,
        )
        profile = InvestorProfile(
            investor_id="inv-custom",
            name="自定义投资者",
            capital_cny=200000.0,
            risk_level="C4",
            style="aggressive",
            max_drawdown_pct=25.0,
            constraints=constraints,
            execution=execution,
        )
        assert profile.constraints.max_single_position_pct == 25.0
        assert profile.execution.slippage_bps == 3.0
        assert profile.execution.enable_stop_loss is False


# ── 场景3：Portfolio + AssetEntry + SentinelEntry 嵌套列表 ──────


class TestPortfolioNested:
    """Portfolio 嵌套 AssetEntry / SentinelEntry。"""

    def test_asset_entry_defaults(self):
        """AssetEntry.asset_type 默认 STOCK，target_weight_pct 范围校验。"""
        entry = AssetEntry(ticker="000001")
        assert entry.asset_type == AssetType.STOCK
        assert entry.target_weight_pct == 0.0
        assert entry.category == AssetCategory.LARGE_CAP

    def test_asset_entry_weight_range(self):
        """target_weight_pct ge=0, le=100。"""
        AssetEntry(ticker="000001", target_weight_pct=0)
        AssetEntry(ticker="000001", target_weight_pct=100)
        with pytest.raises(ValidationError):
            AssetEntry(ticker="000001", target_weight_pct=-0.1)
        with pytest.raises(ValidationError):
            AssetEntry(ticker="000001", target_weight_pct=100.1)

    def test_sentinel_entry_defaults(self):
        """SentinelEntry.layer 默认 'macro'。"""
        entry = SentinelEntry(ticker="510300", name="沪深300ETF")
        assert entry.layer == "macro"
        assert entry.weight == 1.0

    def test_portfolio_with_assets_and_sentinels(self):
        """含 assets 和 sentinels 的 Portfolio 构造。"""
        assets = [
            AssetEntry(ticker="000001", name="平安银行", target_weight_pct=20),
            AssetEntry(ticker="600519", name="贵州茅台", target_weight_pct=25),
        ]
        sentinels = [
            SentinelEntry(ticker="510300", name="沪深300", layer="macro"),
            SentinelEntry(ticker="159915", name="创业板", layer="execution"),
        ]
        portfolio = Portfolio(
            portfolio_id="pf-test",
            investor_id="inv-test",
            assets=assets,
            sentinels=sentinels,
        )
        assert len(portfolio.assets) == 2
        assert len(portfolio.sentinels) == 2
        assert portfolio.assets[0].ticker == "000001"
        assert portfolio.sentinels[1].layer == "execution"
        assert portfolio.benchmark == "000300"

    def test_portfolio_default_empty_lists(self):
        """assets 和 sentinels 默认为空列表。"""
        portfolio = Portfolio(
            portfolio_id="pf-test", investor_id="inv-test",
        )
        assert portfolio.assets == []
        assert portfolio.sentinels == []


# ── 场景4：Transaction 模型全字段 ─────────────────────────────────


class TestTransactionModel:
    """Transaction 模型字段校验。"""

    def test_full_construction(self):
        """所有字段正确构造。"""
        tx = Transaction(
            ticker="000001",
            tx_type=TransactionType.BUY,
            quantity=100.0,
            price=10.0,
            fee=1.5,
            asset_type=AssetType.STOCK,
            investor_id="inv-001",
            portfolio_id="port-001",
            tags=["batch1"],
            reason="测试买入",
        )
        assert tx.ticker == "000001"
        assert tx.tx_type == TransactionType.BUY
        assert tx.quantity == 100.0
        assert tx.price == 10.0
        assert tx.fee == 1.5
        assert tx.status == TransactionStatus.PENDING
        assert tx.idempotency_key == ""
        assert tx.tags == ["batch1"]

    def test_fee_defaults_to_zero(self):
        """fee 默认 0 且 ge=0。"""
        tx = Transaction(
            ticker="000001",
            tx_type=TransactionType.BUY,
            quantity=100.0,
            price=10.0,
        )
        assert tx.fee == 0.0

    def test_fee_non_negative(self):
        """fee 不能为负。"""
        with pytest.raises(ValidationError):
            Transaction(
                ticker="000001",
                tx_type=TransactionType.BUY,
                quantity=100.0,
                price=10.0,
                fee=-0.01,
            )

    def test_quantity_zero_raises(self):
        """quantity=0 抛出 ValidationError（gt=0）。"""
        with pytest.raises(ValidationError):
            Transaction(
                ticker="000001",
                tx_type=TransactionType.BUY,
                quantity=0,
                price=10.0,
            )

    def test_price_zero_raises(self):
        """price=0 抛出 ValidationError（gt=0）。"""
        with pytest.raises(ValidationError):
            Transaction(
                ticker="000001",
                tx_type=TransactionType.BUY,
                quantity=100.0,
                price=0,
            )

    def test_idempotency_key_default_empty(self):
        """idempotency_key 默认为空串。"""
        tx = Transaction(
            ticker="000001",
            tx_type=TransactionType.BUY,
            quantity=100.0,
            price=10.0,
        )
        assert tx.idempotency_key == ""

    def test_status_defaults_to_pending(self):
        """status 默认 PENDING。"""
        tx = Transaction(
            ticker="000001",
            tx_type=TransactionType.BUY,
            quantity=100.0,
            price=10.0,
        )
        assert tx.status == TransactionStatus.PENDING

    def test_tags_default_empty_list(self):
        """tags 默认空列表。"""
        tx = Transaction(
            ticker="000001",
            tx_type=TransactionType.BUY,
            quantity=100.0,
            price=10.0,
        )
        assert tx.tags == []


# ── 场景5：DecisionRecord 模型（含 alias）─────────────────────────


class TestDecisionRecordModel:
    """DecisionRecord 模型 + populate_by_name + alias。"""

    def test_minimal_construction(self):
        """ticker + action 必填。"""
        dr = DecisionRecord(ticker="000001", action="buy")
        assert dr.ticker == "000001"
        assert dr.action == "buy"
        assert dr.status == DecisionStatus.DRAFT
        assert dr.confidence == 0.0

    def test_confidence_range(self):
        """confidence 范围 [0, 1]。"""
        DecisionRecord(ticker="000001", action="buy", confidence=0.0)
        DecisionRecord(ticker="000001", action="buy", confidence=1.0)
        with pytest.raises(ValidationError):
            DecisionRecord(ticker="000001", action="buy", confidence=-0.1)
        with pytest.raises(ValidationError):
            DecisionRecord(ticker="000001", action="buy", confidence=1.1)

    def test_status_default_draft(self):
        """status 默认 DRAFT。"""
        dr = DecisionRecord(ticker="000001", action="buy")
        assert dr.status == DecisionStatus.DRAFT

    def test_execution_tx_id_alias(self):
        """alias execution_tx_id → tx_id 生效。"""
        dr = DecisionRecord(
            ticker="000001", action="buy", execution_tx_id="tx-test-001",
        )
        assert dr.tx_id == "tx-test-001"

    def test_tx_id_direct(self):
        """直接用字段名 tx_id 也可传入。"""
        dr = DecisionRecord(
            ticker="000001", action="buy", tx_id="tx-test-002",
        )
        assert dr.tx_id == "tx-test-002"

    def test_timestamp_alias(self):
        """alias timestamp → created_at 生效。"""
        dr = DecisionRecord(
            ticker="000001", action="buy", timestamp="2025-01-15T10:00:00",
        )
        assert dr.created_at == "2025-01-15T10:00:00"

    def test_populate_by_name_both_ways(self):
        """populate_by_name=True：两种方式均可构造。"""
        dr1 = DecisionRecord(ticker="000001", action="buy", execution_tx_id="tx-a")
        dr2 = DecisionRecord(ticker="000001", action="buy", tx_id="tx-a")
        assert dr1.tx_id == dr2.tx_id == "tx-a"

    def test_team_signals_default(self):
        """team_signals 默认空列表。"""
        dr = DecisionRecord(ticker="000001", action="buy")
        assert dr.team_signals == []


# ── 场景6：序列化/反序列化往返 ─────────────────────────────────────


class TestSerializationRoundTrip:
    """model_dump() → Model(**dict) 往返一致性。"""

    def test_transaction_round_trip(self):
        """Transaction 序列化往返。"""
        tx = Transaction(
            ticker="000001",
            tx_type=TransactionType.BUY,
            quantity=100.0,
            price=10.0,
            fee=1.5,
            asset_type=AssetType.STOCK,
            status=TransactionStatus.EXECUTED,
        )
        dumped = tx.model_dump()
        restored = Transaction(**dumped)
        assert restored.ticker == tx.ticker
        assert restored.tx_type == tx.tx_type
        assert restored.quantity == tx.quantity
        assert restored.price == tx.price
        assert restored.fee == tx.fee
        assert restored.asset_type == tx.asset_type
        assert restored.status == tx.status

    def test_transaction_enum_serialization(self):
        """enum 字段 .value 序列化：'buy' 字符串可从 model_dump 恢复。"""
        tx = Transaction(
            ticker="000001",
            tx_type=TransactionType.BUY,
            quantity=100.0,
            price=10.0,
        )
        dumped = tx.model_dump()
        assert dumped["tx_type"] == "buy"
        # 反序列化
        restored = Transaction(**dumped)
        assert restored.tx_type == TransactionType.BUY

    def test_decision_record_round_trip(self):
        """DecisionRecord 序列化往返。"""
        dr = DecisionRecord(
            ticker="000001",
            action="buy",
            confidence=0.85,
            reasoning="测试决策理由",
            execution_tx_id="tx-test-001",
        )
        dumped = dr.model_dump()
        # 注意：alias 影响 dump key
        restored = DecisionRecord(**dumped)
        assert restored.ticker == dr.ticker
        assert restored.action == dr.action
        assert restored.confidence == dr.confidence
        assert restored.tx_id == dr.tx_id

    def test_portfolio_state_round_trip(self):
        """PortfolioState 序列化往返包含嵌套 CashState/PositionState。"""
        state = PortfolioState(
            investor_id="inv-001",
            portfolio_id="port-001",
            total_assets=105000.0,
            total_market_value=100000.0,
            cash=CashState(total_cash=5000.0, available_cash=5000.0),
            positions=[
                PositionState(
                    ticker="000001",
                    quantity=1000.0,
                    avg_cost=9.5,
                    current_price=10.0,
                    market_value=10000.0,
                    weight_pct=9.52,
                ),
            ],
            nav=1.05,
            total_return_pct=5.0,
        )
        dumped = state.model_dump()
        restored = PortfolioState(**dumped)
        assert restored.investor_id == state.investor_id
        assert restored.total_assets == state.total_assets
        assert restored.nav == state.nav
        assert len(restored.positions) == 1
        assert restored.positions[0].ticker == "000001"
        assert restored.cash.total_cash == 5000.0

    def test_decision_record_alias_dump(self):
        """DecisionRecord model_dump 使用 alias 键名。"""
        dr = DecisionRecord(
            ticker="000001",
            action="buy",
            execution_tx_id="tx-x",
            timestamp="2025-01-15T10:00:00",
        )
        # model_dump(by_alias=True) 使用 alias 键
        dumped_alias = dr.model_dump(by_alias=True)
        assert "execution_tx_id" in dumped_alias
        assert "timestamp" in dumped_alias


# ── 场景7：PortfolioState + CashState + PositionState 嵌套 ─────────


class TestPortfolioStateNested:
    """PortfolioState 嵌套子模型。"""

    def test_cash_default_factory(self):
        """cash 子对象默认工厂自动创建。"""
        state = PortfolioState(
            investor_id="inv-001", portfolio_id="port-001",
        )
        assert isinstance(state.cash, CashState)
        assert state.cash.total_cash == 0.0
        assert state.cash.available_cash == 0.0
        assert state.cash.frozen_cash == 0.0

    def test_position_defaults(self):
        """PositionState weight_pct/today_change_pct 默认值。"""
        pos = PositionState(ticker="000001")
        assert pos.weight_pct == 0.0
        assert pos.today_change_pct == 0.0
        assert pos.quantity == 0.0
        assert pos.avg_cost == 0.0
        assert pos.current_price == 0.0
        assert pos.market_value == 0.0

    def test_nav_default(self):
        """nav 默认 1.0。"""
        state = PortfolioState(
            investor_id="inv-001", portfolio_id="port-001",
        )
        assert state.nav == 1.0

    def test_full_state_construction(self):
        """完整 PortfolioState 含多个持仓。"""
        state = PortfolioState(
            investor_id="inv-001",
            portfolio_id="port-001",
            total_assets=200_000.0,
            total_market_value=190_000.0,
            cash=CashState(total_cash=10_000.0, available_cash=10_000.0),
            positions=[
                PositionState(
                    ticker="000001", quantity=500, avg_cost=9.0,
                    current_price=10.0, market_value=5000.0,
                    unrealized_pnl=500.0, weight_pct=2.5,
                    today_change_pct=1.5,
                ),
                PositionState(
                    ticker="600519", quantity=100, avg_cost=1800.0,
                    current_price=1850.0, market_value=185000.0,
                    unrealized_pnl=5000.0, weight_pct=92.5,
                    today_change_pct=-0.5,
                ),
            ],
            nav=1.05,
            benchmark_nav=1.03,
            total_return_pct=5.0,
        )
        assert state.total_assets == 200_000.0
        assert len(state.positions) == 2
        assert state.positions[0].unrealized_pnl == 500.0
        assert state.positions[1].market_value == 185000.0
        assert state.nav == 1.05
        assert state.benchmark_nav == 1.03

    def test_snapshot_time_default(self):
        """snapshot_time 默认工厂生成 ISO 格式时间。"""
        state = PortfolioState(
            investor_id="inv-001", portfolio_id="port-001",
        )
        assert state.snapshot_time
        assert "T" in state.snapshot_time


# ── 场景8：ReviewSnapshot 全维度聚合 ──────────────────────────────


class TestReviewSnapshot:
    """ReviewSnapshot 7 维度复盘快照。"""

    def test_snapshot_type_required(self):
        """snapshot_type 必填。"""
        with pytest.raises(ValidationError):
            ReviewSnapshot()

    def test_all_dimensions_optional_default_none(self):
        """各维度 Optional 默认 None。"""
        rs = ReviewSnapshot(snapshot_type="full")
        assert rs.snapshot_type == "full"
        assert rs.portfolio is None
        assert rs.market is None
        assert rs.sentinel is None
        assert rs.performance is None
        assert rs.decision_reviews is None
        assert rs.valuation is None
        assert rs.cascade is None

    def test_period_default_factory(self):
        """period 默认工厂不抛异常，ReviewPeriod 有默认空值。"""
        rs = ReviewSnapshot(snapshot_type="full")
        assert isinstance(rs.period, ReviewPeriod)
        assert rs.period.start == ""

    def test_full_seven_dimensions(self):
        """构造含全部 7 个维度的复盘快照。"""
        rs = ReviewSnapshot(
            snapshot_type="full",
            generated_at="2025-01-15T10:00:00",
            period=ReviewPeriod(start="2025-01-06", end="2025-01-12", label="2025-W2"),
            portfolio=PortfolioDimension(total_assets=105000.0, nav=1.05, positions=4),
            market=MarketDimension(
                index_code="000300",
                weekly_change_pct=1.5,
                volume_trend="放量",
            ),
            sentinel=SentinelDimension(
                overall_signal="攻防转换期",
                bullish_count=3,
                total=8,
                position_limit_pct=20.0,
            ),
            performance=PerformanceDimension(
                total_return=5.0,
                annualized_return=12.5,
                max_drawdown=-3.2,
                win_rate=0.65,
            ),
            decision_reviews=DecisionReviewDimension(
                total_decisions=5,
                filled_count=3,
                pending_5d=2,
            ),
            valuation=ValuationDimension(
                pe_percentile=45.5,
                level="fair",
                current_pe=18.5,
            ),
            cascade=CascadeDimension(
                mode="monthly",
                max_drawdown=-8.5,
                sharpe_ratio=1.2,
            ),
        )
        assert rs.snapshot_type == "full"
        assert rs.portfolio is not None
        assert rs.market is not None
        assert rs.sentinel is not None
        assert rs.performance is not None
        assert rs.decision_reviews is not None
        assert rs.valuation is not None
        assert rs.cascade is not None

    def test_snapshot_type_values(self):
        """snapshot_type 支持 4 种类型字符串。"""
        for st in ["full", "market_weekly", "cascade_monthly", "decision_review"]:
            rs = ReviewSnapshot(snapshot_type=st)
            assert rs.snapshot_type == st

    def test_market_dimension_ma_positions(self):
        """MarketDimension ma_positions 默认空 dict。"""
        md = MarketDimension()
        assert md.ma_positions == {}
        assert md.macro_events == []
        md2 = MarketDimension(ma_positions={"MA5": "上方", "MA20": "下方"})
        assert md2.ma_positions["MA5"] == "上方"

    def test_cascade_dimension_extra_ignore(self):
        """CascadeDimension model_config extra='ignore' 忽略多余字段。"""
        cd = CascadeDimension(
            mode="monthly",
            max_drawdown=-10.0,
            extra_field="should_be_ignored",  # type: ignore
        )
        # Should not raise — extra field ignored
        assert cd.mode == "monthly"
        assert cd.max_drawdown == -10.0
