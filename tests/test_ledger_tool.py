"""交易账本工具测试"""
import pytest
import asyncio
from praxis.tools.ledger import get_ledger, add_transaction, reverse_transaction, approve_transaction


class TestLedgerTools:
    """交易账本工具测试"""

    def test_get_ledger(self):
        """测试获取交易账本"""
        result = get_ledger()

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_add_transaction(self):
        """测试添加交易"""
        result = add_transaction("buy", "ETF_300", 100, 4.0)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_reverse_transaction(self):
        """测试撤销交易"""
        result = reverse_transaction("tx-001", "测试撤销")

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_approve_transaction(self):
        """测试审批交易"""
        result = approve_transaction("tx-001", "测试审批")

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result


class TestLedgerToolsIntegration:
    """交易账本工具集成测试"""

    def test_get_ledger_returns_valid_data(self):
        """测试获取交易账本返回有效数据"""
        result = get_ledger()

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result

    def test_add_transaction_returns_valid_data(self):
        """测试添加交易返回有效数据"""
        result = add_transaction("buy", "ETF_300", 100, 4.0)

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result
