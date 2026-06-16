"""复盘回填器测试"""
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile

from praxis.engine.review_filler import ReviewFiller, ReviewSummary
from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.core.ledger import FileLedger
from praxis.core.models.decision import DecisionRecord, DecisionStatus


class MockDataProvider:
    """模拟数据源"""

    def get_market_data(self, ticker, start_date, end_date):
        """模拟获取市场数据"""
        return [
            {"date": "2026-01-01", "close": 10.0},
            {"date": "2026-06-01", "close": 11.0},
        ]


class TestReviewFiller:
    """复盘回填器测试"""

    def setup_method(self):
        """测试前准备"""
        # 创建临时目录
        self.tmp_dir = tempfile.mkdtemp()
        self.recorder = FileDecisionRecorder(Path(self.tmp_dir) / "decisions")
        self.ledger = FileLedger(Path(self.tmp_dir) / "ledger")
        self.data_provider = MockDataProvider()
        self.filler = ReviewFiller(
            self.recorder, self.ledger, self.data_provider
        )

    def test_fill_pending_reviews(self):
        """测试回填待复盘决策"""
        # 添加测试决策
        decision = DecisionRecord(
            decision_id="dc-001",
            timestamp=datetime.now(timezone.utc) - timedelta(days=10),
            ticker="ETF_300",
            action="buy",
            confidence=0.8,
            reasoning="测试决策",
            status=DecisionStatus.EXECUTED,
            execution_tx_id="tx-001",
        )
        self.recorder.create(decision)

        # 添加测试交易
        from praxis.core.models.transaction import Transaction, TransactionType
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=10.0,
            fee=5.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 运行回填
        import asyncio
        results = asyncio.run(self.filler.fill_pending_reviews())

        # 验证结果
        assert isinstance(results, list)

    def test_fill_5d_review(self):
        """测试 5 日复盘回填"""
        # 添加测试决策（5 天前）
        decision = DecisionRecord(
            decision_id="dc-001",
            timestamp=datetime.now(timezone.utc) - timedelta(days=6),
            ticker="ETF_300",
            action="buy",
            confidence=0.8,
            reasoning="测试决策",
            status=DecisionStatus.EXECUTED,
            execution_tx_id="tx-001",
        )
        self.recorder.create(decision)

        # 添加测试交易
        from praxis.core.models.transaction import Transaction, TransactionType
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=10.0,
            fee=5.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=6),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 运行回填
        import asyncio
        results = asyncio.run(self.filler.fill_pending_reviews())

        # 验证结果
        assert isinstance(results, list)

    def test_get_review_summary(self):
        """测试获取复盘汇总"""
        # 添加测试决策
        decision = DecisionRecord(
            decision_id="dc-001",
            timestamp=datetime.now(timezone.utc),
            ticker="ETF_300",
            action="buy",
            confidence=0.8,
            reasoning="测试决策",
            status=DecisionStatus.EXECUTED,
        )
        self.recorder.create(decision)

        # 获取汇总
        summary = self.filler.get_summary()

        # 验证汇总
        assert isinstance(summary, ReviewSummary)
        assert summary.total_decisions >= 1

    def test_calculate_return(self):
        """测试收益率计算"""
        # 测试收益率计算
        entry_price = 10.0
        current_price = 11.0
        expected_return = 0.1  # 10%

        # 计算收益率
        actual_return = (current_price - entry_price) / entry_price
        assert abs(actual_return - expected_return) < 0.001

    def test_days_since(self):
        """测试天数计算"""
        # 测试天数计算
        past_time = datetime.now(timezone.utc) - timedelta(days=5)
        days = self.filler._days_since(past_time)
        assert days >= 5

    def test_get_execution_price(self):
        """测试获取执行价格"""
        # 添加测试决策
        decision = DecisionRecord(
            decision_id="dc-001",
            timestamp=datetime.now(timezone.utc),
            ticker="ETF_300",
            action="buy",
            confidence=0.8,
            reasoning="测试决策",
            status=DecisionStatus.EXECUTED,
            execution_tx_id="tx-001",
        )
        self.recorder.create(decision)

        # 添加测试交易
        from praxis.core.models.transaction import Transaction, TransactionType
        tx = Transaction(
            tx_id="tx-001",
            type=TransactionType.BUY,
            ticker="ETF_300",
            quantity=1000,
            price=10.0,
            fee=5.0,
            created_at=datetime.now(timezone.utc),
            status="confirmed",
        )
        self.ledger.append(tx)

        # 获取执行价格
        price = self.filler._get_execution_price(decision)
        assert price == 10.0
