"""数据质量检查引擎测试 — DataQualityChecker."""
from __future__ import annotations

import pytest

from praxis.core.models import Transaction, TransactionType, TransactionStatus
from praxis.engine.data_quality import DataQualityChecker
from praxis.engine.tests.conftest import FakeLedger, FakeDataProvider


class TestCheckCompleteness:
    """完整性检查测试."""

    def test_completeness_normal(self):
        """正常数据完整性检查."""
        checker = DataQualityChecker()
        ledger = FakeLedger([
            Transaction(
                tx_id="tx-001", ticker="600519", tx_type=TransactionType.BUY,
                quantity=100, price=1850, status=TransactionStatus.EXECUTED,
            ),
            Transaction(
                tx_id="tx-002", ticker="159915", tx_type=TransactionType.SELL,
                quantity=5000, price=2.35, status=TransactionStatus.EXECUTED,
            ),
        ])
        result = checker.check_completeness(ledger)
        assert result["name"] == "completeness"
        assert result["status"] in ("pass", "warn", "fail")
        assert result["details"]["total_records"] == 2
        assert result["details"]["missing_fields"] == 0
        assert result["details"]["duplicate_records"] == 0

    def test_completeness_with_missing_fields(self):
        """缺失必填字段检测."""
        checker = DataQualityChecker()
        # 创建缺失 ticker 的交易（quantity/price 需 > 0 因为 Pydantic 约束）
        ledger = FakeLedger([
            Transaction(
                tx_id="tx-003", ticker="", tx_type=TransactionType.BUY,
                quantity=100, price=1850, status=TransactionStatus.PENDING,
            ),
        ])
        result = checker.check_completeness(ledger)
        assert result["details"]["total_records"] == 1
        # ticker="" 被检测为缺失
        assert result["details"]["missing_fields"] > 0


class TestCheckConsistency:
    """一致性检查测试."""

    def test_consistency_cross_validation(self):
        """交叉验证持仓数量 vs 账本."""
        checker = DataQualityChecker()
        ledger = FakeLedger([
            Transaction(
                tx_id="tx-001", ticker="600519", tx_type=TransactionType.BUY,
                quantity=100, price=1850, status=TransactionStatus.EXECUTED,
            ),
            Transaction(
                tx_id="tx-002", ticker="600519", tx_type=TransactionType.BUY,
                quantity=50, price=1900, status=TransactionStatus.EXECUTED,
            ),
            Transaction(
                tx_id="tx-003", ticker="600519", tx_type=TransactionType.SELL,
                quantity=30, price=1880, status=TransactionStatus.EXECUTED,
            ),
        ])
        provider = FakeDataProvider()
        result = checker.check_consistency(ledger, provider)
        assert result["name"] == "consistency"
        assert "derived_positions" in result["details"]
        derived = result["details"]["derived_positions"]
        assert "600519" in derived
        # buy 100 + buy 50 - sell 30 = 120
        assert derived["600519"] == 120.0

    def test_consistency_zero_balance(self):
        """零余额持仓被标记."""
        checker = DataQualityChecker()
        ledger = FakeLedger([
            Transaction(
                tx_id="tx-001", ticker="600519", tx_type=TransactionType.BUY,
                quantity=100, price=1850, status=TransactionStatus.EXECUTED,
            ),
            Transaction(
                tx_id="tx-002", ticker="600519", tx_type=TransactionType.SELL,
                quantity=100, price=1880, status=TransactionStatus.EXECUTED,
            ),
        ])
        provider = FakeDataProvider()
        result = checker.check_consistency(ledger, provider)
        derived = result["details"]["derived_positions"]
        assert derived["600519"] == 0.0


class TestCheckTimeliness:
    """时效性检查测试."""

    def test_timeliness_normal(self):
        """时效性检查正常返回."""
        checker = DataQualityChecker()
        provider = FakeDataProvider()
        result = checker.check_timeliness(provider)
        assert result["name"] == "timeliness"
        assert result["status"] in ("pass", "warn", "fail")
        assert "check_time" in result["details"]
        assert result["details"]["max_stale_hours"] == 24


class TestRunAllChecks:
    """聚合检查测试."""

    def test_run_all_checks(self):
        """运行全部 3 项检查并聚合."""
        checker = DataQualityChecker()
        ledger = FakeLedger([
            Transaction(
                tx_id="tx-001", ticker="600519", tx_type=TransactionType.BUY,
                quantity=100, price=1850, status=TransactionStatus.EXECUTED,
            ),
        ])
        provider = FakeDataProvider()
        result = checker.run_all_checks(ledger, provider)
        assert "overall_status" in result
        assert result["overall_status"] in ("pass", "warn", "fail")
        assert len(result["checks"]) == 3
        assert all("name" in c and "status" in c and "details" in c for c in result["checks"])


class TestEmptyLedger:
    """空账本测试."""

    def test_empty_ledger(self):
        """空账本正常返回."""
        checker = DataQualityChecker()
        ledger = FakeLedger()
        provider = FakeDataProvider()

        result = checker.check_completeness(ledger)
        assert result["status"] == "warn"
        assert result["details"]["total_records"] == 0

        result = checker.check_consistency(ledger, provider)
        assert result["status"] == "warn"

    def test_run_all_checks_empty(self):
        """空账本聚合检查."""
        checker = DataQualityChecker()
        ledger = FakeLedger()
        provider = FakeDataProvider()
        result = checker.run_all_checks(ledger, provider)
        assert "overall_status" in result
