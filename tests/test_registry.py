"""数据源注册表测试"""
import pytest
import asyncio
from praxis.engine.data.registry import ProviderRegistry
from praxis.core.interfaces import DataProvider


# ── 测试用 Mock Provider ──

class MockProviderA(DataProvider):
    """模拟数据源 A（优先级高）"""
    async def get_realtime_quote(self, tickers):
        return {t: {"price": 10.0, "source": "mock_a"} for t in tickers}
    async def get_history_kline(self, ticker, period, count):
        return [{"date": "2026-01-01", "close": 10.0, "source": "mock_a"}]
    async def get_fund_nav(self, ticker):
        return {"ticker": ticker, "nav": 1.0, "source": "mock_a"}
    async def close(self):
        pass


class MockProviderB(DataProvider):
    """模拟数据源 B（优先级低）"""
    async def get_realtime_quote(self, tickers):
        return {t: {"price": 20.0, "source": "mock_b"} for t in tickers}
    async def get_history_kline(self, ticker, period, count):
        return [{"date": "2026-01-01", "close": 20.0, "source": "mock_b"}]
    async def get_fund_nav(self, ticker):
        return {"ticker": ticker, "nav": 2.0, "source": "mock_b"}
    async def close(self):
        pass


class FailingProvider(DataProvider):
    """模拟失败的数据源"""
    async def get_realtime_quote(self, tickers):
        raise Exception("模拟失败")
    async def get_history_kline(self, ticker, period, count):
        raise Exception("模拟失败")
    async def get_fund_nav(self, ticker):
        raise Exception("模拟失败")
    async def close(self):
        pass


class TestProviderRegistry:
    """注册表测试"""

    def setup_method(self):
        self.registry = ProviderRegistry()

    def test_register_and_list(self):
        """注册并列出数据源"""
        self.registry.register("mock_a", MockProviderA, priority=10)
        self.registry.register("mock_b", MockProviderB, priority=20)
        providers = self.registry.list_providers()
        assert len(providers) == 2
        assert providers[0]["name"] == "mock_a"
        assert providers[0]["priority"] == 10

    def test_get_chain_priority_order(self):
        """按优先级排序返回"""
        self.registry.register("low", MockProviderB, priority=80)
        self.registry.register("high", MockProviderA, priority=10)
        chain = self.registry.get_chain()
        assert chain[0][0] == "high"
        assert chain[1][0] == "low"

    def test_disabled_provider_excluded(self):
        """禁用的数据源不参与"""
        self.registry.register("a", MockProviderA, priority=10, enabled=True)
        self.registry.register("b", MockProviderB, priority=20, enabled=False)
        chain = self.registry.get_chain()
        assert len(chain) == 1
        assert chain[0][0] == "a"

    def test_health_check_failure(self):
        """连续失败后标记为 unhealthy"""
        self.registry.register("fail", FailingProvider, priority=10)

        # 前 2 次失败仍可用
        self.registry.report_failure("fail")
        self.registry.report_failure("fail")
        entry = self.registry._entries["fail"]
        assert entry.healthy is True

        # 第 3 次失败标记为 unhealthy
        self.registry.report_failure("fail")
        assert entry.healthy is False

        # 不再出现在 chain 中
        chain = self.registry.get_chain()
        assert len(chain) == 0

    def test_health_recovery(self):
        """成功调用恢复健康状态"""
        self.registry.register("fail", FailingProvider, priority=10)
        self.registry.report_failure("fail")
        self.registry.report_failure("fail")
        self.registry.report_failure("fail")
        assert self.registry._entries["fail"].healthy is False

        self.registry.report_success("fail")
        assert self.registry._entries["fail"].healthy is True
        assert self.registry._entries["fail"].failure_count == 0

    def test_unregister(self):
        """注销数据源"""
        self.registry.register("a", MockProviderA, priority=10)
        assert len(self.registry.list_providers()) == 1
        self.registry.unregister("a")
        assert len(self.registry.list_providers()) == 0

    def test_apply_config(self):
        """配置覆盖优先级"""
        self.registry.register("a", MockProviderA, priority=50)
        self.registry.apply_config({
            "provider_registry": {
                "a": {"priority": 5, "enabled": False}
            }
        })
        entry = self.registry._entries["a"]
        assert entry.priority == 5
        assert entry.enabled is False


class TestProviderChain:
    """数据源链式容错测试"""

    def test_chain_returns_working_provider(self):
        """chain 返回可用的数据源"""
        registry = ProviderRegistry()
        registry.register("a", MockProviderA, priority=10)
        chain = registry.get_chain()
        assert len(chain) == 1

        result = asyncio.get_event_loop().run_until_complete(
            chain[0][1].get_realtime_quote(["600995"])
        )
        assert result["600995"]["source"] == "mock_a"


class TestBuiltinDiscovery:
    """内置数据源发现测试"""

    def test_discover_eastmoney(self):
        """东方财富始终可用"""
        registry = ProviderRegistry()
        registry._discover_builtin()
        names = [p["name"] for p in registry.list_providers()]
        assert "eastmoney" in names
        assert "tencent" in names

    def test_discover_akshare_if_installed(self):
        """AKShare 按需加载"""
        registry = ProviderRegistry()
        registry._discover_builtin()
        names = [p["name"] for p in registry.list_providers()]
        # 如果安装了 akshare 则存在，否则不存在
        try:
            import akshare
            assert "akshare" in names
        except ImportError:
            assert "akshare" not in names

    def test_discover_baostock_if_installed(self):
        """Baostock 按需加载"""
        registry = ProviderRegistry()
        registry._discover_builtin()
        names = [p["name"] for p in registry.list_providers()]
        # baostock 已安装（本系统），所以应该被发现
        assert "baostock" in names
