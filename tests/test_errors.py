"""E2.5 — 错误路径测试"""
import os
import pytest

from praxis.core.models.error import PraxisError, ConfigError, DataError, ReconcileError, LedgerError, ConstraintViolation
from praxis.engine.config_loader import YamlConfigLoader
from praxis.core.ledger import FileLedger
from praxis.tools.portfolio import get_portfolio
from praxis.tools.ledger import add_transaction
from praxis.tools.decision import get_decision_record


class TestConfigErrors:
    """配置错误测试"""

    def test_nonexistent_investor(self):
        """不存在的投资者"""
        workspace = os.environ.get("PRAXIS_WORKSPACE", ".")
        loader = YamlConfigLoader(workspace)
        with pytest.raises(ConfigError) as exc_info:
            loader.load_investor("nonexistent")
        assert "不存在" in str(exc_info.value)

    def test_nonexistent_portfolio(self):
        """不存在的组合"""
        workspace = os.environ.get("PRAXIS_WORKSPACE", ".")
        loader = YamlConfigLoader(workspace)
        with pytest.raises(ConfigError) as exc_info:
            loader.load_portfolio("example", "nonexistent")
        assert "不存在" in str(exc_info.value)

    def test_nonexistent_strategy(self):
        """不存在的策略"""
        workspace = os.environ.get("PRAXIS_WORKSPACE", ".")
        loader = YamlConfigLoader(workspace)
        with pytest.raises(ConfigError) as exc_info:
            loader.load_strategy("nonexistent")
        assert "不存在" in str(exc_info.value)


class TestLedgerErrors:
    """账本错误测试"""

    def test_reverse_nonexistent(self, tmp_path):
        """冲销不存在的交易"""
        ledger_path = tmp_path / "test.jsonl"
        ledger = FileLedger(ledger_path)
        with pytest.raises(LedgerError):
            ledger.reverse("tx-nonexistent", "测试")


class TestToolErrors:
    """工具错误测试"""

    def test_get_portfolio_error(self):
        """获取不存在的组合"""
        result = get_portfolio("example", "nonexistent")
        assert result["success"] is False
        assert "error" in result

    def test_get_decision_nonexistent(self):
        """获取不存在的决策"""
        result = get_decision_record("dc-nonexistent")
        assert result["success"] is False
        assert "不存在" in result["error"]


class TestErrorHierarchy:
    """错误层次结构测试"""

    def test_praxis_error_base(self):
        """PraxisError 是所有错误的基类"""
        assert issubclass(ConfigError, PraxisError)
        assert issubclass(DataError, PraxisError)
        assert issubclass(ReconcileError, PraxisError)
        assert issubclass(LedgerError, PraxisError)
        assert issubclass(ConstraintViolation, PraxisError)

    def test_error_to_dict(self):
        """错误可以序列化为字典"""
        error = PraxisError("测试", code="TEST", details={"key": "value"})
        d = error.to_dict()
        assert d["error"] == "TEST"
        assert d["message"] == "测试"
        assert d["details"]["key"] == "value"
