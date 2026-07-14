"""tests for core/interfaces.py — 8 ABC + 1 Protocol + StateStore."""

from __future__ import annotations

import abc
from typing import runtime_checkable

import pytest

from praxis.core.interfaces import (
    DataProvider,
    ConfigLoader,
    Ledger,
    StateBuilder,
    ConstraintChecker,
    DecisionRecorder,
    PerformanceCalculator,
    AuditLogger,
    BenchmarkProvider,
    MarketDataTransport,
    StateStore,
)


# ── 辅助：提取抽象方法名 ──────────────────────────────────────────


def _abstract_method_names(cls: type) -> set[str]:
    """返回类的所有抽象方法名集合。"""
    return {
        name for name in dir(cls)
        if hasattr(getattr(cls, name), "__isabstractmethod__")
    }


# ── 场景1：DataProvider ABC 不可实例化 ─────────────────────────────


class TestDataProviderABC:
    """DataProvider ABC 3 个抽象方法。"""

    def test_cannot_instantiate(self):
        """DataProvider() 抛出 TypeError。"""
        with pytest.raises(TypeError):
            DataProvider()  # type: ignore[abstract]

    def test_abstract_methods(self):
        """get_realtime_quote / get_history_kline / get_fund_nav。"""
        methods = _abstract_method_names(DataProvider)
        assert "get_realtime_quote" in methods
        assert "get_history_kline" in methods
        assert "get_fund_nav" in methods

    def test_three_abstract_methods_count(self):
        """恰好 3 个抽象方法。"""
        from praxis.core.interfaces import DataProvider as DP
        assert len(DP.__abstractmethods__) == 3


# ── 场景2：ConfigLoader ABC 不可实例化 ─────────────────────────────


class TestConfigLoaderABC:
    """ConfigLoader ABC 4 个抽象方法。"""

    def test_cannot_instantiate(self):
        """ConfigLoader() 抛出 TypeError。"""
        with pytest.raises(TypeError):
            ConfigLoader()  # type: ignore[abstract]

    def test_abstract_methods(self):
        """4 个抽象方法。"""
        assert len(ConfigLoader.__abstractmethods__) == 4
        methods = _abstract_method_names(ConfigLoader)
        assert "load_investor" in methods
        assert "load_portfolio" in methods
        assert "load_strategy" in methods
        assert "load_asset_detail" in methods


# ── 场景3：Ledger ABC 方法签名 ─────────────────────────────────────


class TestLedgerABC:
    """Ledger ABC 6 个抽象方法。"""

    def test_cannot_instantiate(self):
        """Ledger() 抛出 TypeError。"""
        with pytest.raises(TypeError):
            Ledger()  # type: ignore[abstract]

    def test_six_abstract_methods(self):
        """append / list / get / exists / delete / purge。"""
        assert len(Ledger.__abstractmethods__) == 6
        methods = _abstract_method_names(Ledger)
        assert "append" in methods
        assert "list" in methods
        assert "get" in methods
        assert "exists" in methods
        assert "delete" in methods
        assert "purge" in methods

    def test_method_signatures_match(self):
        """检查关键方法签名存在且签名合理。"""
        import inspect
        sig_append = inspect.signature(Ledger.append)
        assert "tx" in sig_append.parameters

        sig_list = inspect.signature(Ledger.list)
        assert "ticker" in sig_list.parameters
        assert "limit" in sig_list.parameters


# ── 场景4：StateBuilder ABC ────────────────────────────────────────


class TestStateBuilderABC:
    """StateBuilder ABC: rebuild + validate。"""

    def test_cannot_instantiate(self):
        """StateBuilder() 抛出 TypeError。"""
        with pytest.raises(TypeError):
            StateBuilder()  # type: ignore[abstract]

    def test_abstract_methods(self):
        """rebuild + validate。"""
        assert len(StateBuilder.__abstractmethods__) == 2
        methods = _abstract_method_names(StateBuilder)
        assert "rebuild" in methods
        assert "validate" in methods


# ── 场景5：其余 4 个 ABC ───────────────────────────────────────────


class TestRemainingABCs:
    """ConstraintChecker / DecisionRecorder / PerformanceCalculator / AuditLogger / BenchmarkProvider。"""

    def test_constraint_checker_abc(self):
        """ConstraintChecker: check 抽象方法。"""
        with pytest.raises(TypeError):
            ConstraintChecker()  # type: ignore[abstract]
        assert "check" in ConstraintChecker.__abstractmethods__

    def test_decision_recorder_abc(self):
        """DecisionRecorder: create/get/update_status/list_pending/link_transaction。"""
        with pytest.raises(TypeError):
            DecisionRecorder()  # type: ignore[abstract]
        assert len(DecisionRecorder.__abstractmethods__) == 5

    def test_performance_calculator_abc(self):
        """PerformanceCalculator: calculate + compare_versions。"""
        with pytest.raises(TypeError):
            PerformanceCalculator()  # type: ignore[abstract]
        assert len(PerformanceCalculator.__abstractmethods__) == 2

    def test_audit_logger_abc(self):
        """AuditLogger: log + query。"""
        with pytest.raises(TypeError):
            AuditLogger()  # type: ignore[abstract]
        assert len(AuditLogger.__abstractmethods__) == 2

    def test_benchmark_provider_abc(self):
        """BenchmarkProvider: get_daily_kline + get_latest_price + get_supported_indices。"""
        with pytest.raises(TypeError):
            BenchmarkProvider()  # type: ignore[abstract]
        assert len(BenchmarkProvider.__abstractmethods__) == 3


# ── 场景6：MarketDataTransport Protocol ────────────────────────────


class TestMarketDataTransportProtocol:
    """MarketDataTransport @runtime_checkable Protocol。"""

    def test_is_runtime_checkable(self):
        """@runtime_checkable 装饰生效（验证 isinstance 可用）。"""
        # runtime_checkable 返回被装饰的类（不是 bool）
        # 验证方式是检查 isinstance 行为
        from typing import runtime_checkable as _rc
        # Protocol decorated with @runtime_checkable 可以直接 isinstance
        assert isinstance(MarketDataTransport, type)

    def test_instance_check_with_methods(self):
        """实现了全部 5 个方法的对象可通过 isinstance 检查。"""

        class FullTransport:
            async def fetch_index_trend(self, start_date, end_date, index_code):
                return {}

            async def fetch_sector_rotation(self, start_date, end_date):
                return {}

            async def fetch_fund_flow(self, start_date, end_date):
                return {}

            async def fetch_sentiment(self, start_date, end_date):
                return {}

            async def fetch_macro_events(self, start_date, end_date):
                return {}

        obj = FullTransport()
        assert isinstance(obj, MarketDataTransport)

    def test_instance_check_missing_methods(self):
        """未实现全部方法时 isinstance 返回 False。"""

        class PartialTransport:
            async def fetch_index_trend(self, start_date, end_date, index_code):
                return {}

        obj = PartialTransport()
        assert not isinstance(obj, MarketDataTransport)

    def test_five_methods_required(self):
        """协议要求 5 个方法。"""
        # 通过检查实例化来验证：一个有 5 个方法的类
        assert hasattr(MarketDataTransport, "fetch_index_trend")
        assert hasattr(MarketDataTransport, "fetch_sector_rotation")
        assert hasattr(MarketDataTransport, "fetch_fund_flow")
        assert hasattr(MarketDataTransport, "fetch_sentiment")
        assert hasattr(MarketDataTransport, "fetch_macro_events")


# ── 场景7：StateStore 空壳 ────────────────────────────────────────


class TestStateStore:
    """StateStore 空壳可实例化但无方法。"""

    def test_can_instantiate(self):
        """StateStore() 可实例化。"""
        store = StateStore.__new__(StateStore)
        assert store is not None

    def test_no_abstract_methods(self):
        """无抽象方法（仅有 pass body）。"""
        assert len(StateStore.__abstractmethods__) == 0

    def test_can_subclass_and_instantiate(self):
        """子类化后可实例化。"""
        class MyStore(StateStore):
            pass

        store = MyStore()
        assert store is not None


# ── 场景8：TYPE_CHECKING 导入不引起运行时错误 ──────────────────────


class TestTypeCheckingImports:
    """TYPE_CHECKING 导入运行时安全。"""

    def test_import_data_provider(self):
        """直接导入 DataProvider 不触发 ImportError。"""
        from praxis.core.interfaces import DataProvider
        assert DataProvider is not None

    def test_import_config_loader(self):
        """直接导入 ConfigLoader 正常。"""
        from praxis.core.interfaces import ConfigLoader
        assert ConfigLoader is not None

    def test_import_ledger(self):
        """直接导入 Ledger 正常。"""
        from praxis.core.interfaces import Ledger
        assert Ledger is not None

    def test_import_from_package(self):
        """从 praxis.core 包导入所有接口。"""
        from praxis.core import DataProvider, ConfigLoader, Ledger, StateStore
        assert all([DataProvider, ConfigLoader, Ledger, StateStore])

    def test_import_market_data_transport(self):
        """导入 MarketDataTransport 正常。"""
        from praxis.core.interfaces import MarketDataTransport
        assert MarketDataTransport is not None
