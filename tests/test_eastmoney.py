"""东方财富数据源测试"""
import pytest
import asyncio
import pytest_asyncio
from praxis.engine.data.eastmoney import (
    EastMoneyDataProvider,
    _detect_market,
    _to_eastmoney_secid,
    _is_fund,
)


class TestTickerConversion:
    """Ticker 格式转换测试"""

    def test_detect_market_sh_stock(self):
        assert _detect_market("000001") == 1

    def test_detect_market_sh_etf(self):
        assert _detect_market("510310") == 1
        assert _detect_market("589850") == 1

    def test_detect_market_sz_stock(self):
        assert _detect_market("000001") == 0
        assert _detect_market("300750") == 0

    def test_detect_market_sz_etf(self):
        assert _detect_market("159915") == 0

    def test_detect_market_fund(self):
        assert _detect_market("016874") == 0
        assert _detect_market("161725") == 0

    def test_to_secid_sh(self):
        assert _to_eastmoney_secid("000001") == "1.600995"
        assert _to_eastmoney_secid("510310") == "1.510310"

    def test_to_secid_sz(self):
        assert _to_eastmoney_secid("000001") == "0.000001"
        assert _to_eastmoney_secid("159915") == "0.159915"

    def test_to_secid_already_formatted(self):
        assert _to_eastmoney_secid("1.600995") == "1.600995"

    def test_is_fund(self):
        assert _is_fund("016874") is True
        assert _is_fund("161725") is True
        assert _is_fund("000001") is False
        assert _is_fund("510310") is False


class TestEastMoneyDataProvider:
    """东方财富数据源集成测试"""

    @pytest_asyncio.fixture
    async def provider(self):
        p = EastMoneyDataProvider()
        yield p
        await p.close()

    @pytest.mark.xfail(reason="网络依赖：非交易时段 API 返回空数据")
    async def test_get_realtime_stock(self, provider):
        """测试股票实时行情"""
        result = await provider.get_realtime_quote(["000001"])
        assert "000001" in result
        q = result["000001"]
        assert q["price"] > 0
        assert q["name"] != ""
        assert q["source"] == "eastmoney"

    @pytest.mark.xfail(reason="网络依赖：非交易时段 API 返回空数据")
    async def test_get_realtime_etf(self, provider):
        """测试 ETF 实时行情"""
        result = await provider.get_realtime_quote(["510310"])
        assert "510310" in result
        q = result["510310"]
        assert q["price"] > 0
        assert q["price"] < 100  # ETF 价格通常 < 100

    async def test_get_realtime_fund(self, provider):
        """测试场外基金净值"""
        result = await provider.get_realtime_quote(["016874"])
        assert "016874" in result
        q = result["016874"]
        assert q["price"] > 0

    @pytest.mark.xfail(reason="网络依赖：非交易时段 API 返回空数据")
    async def test_get_realtime_batch(self, provider):
        """测试批量查询"""
        result = await provider.get_realtime_quote(["000001", "510310"])
        assert len(result) >= 1  # 至少一个成功

    async def test_get_history_kline(self, provider):
        """测试历史K线"""
        klines = await provider.get_history_kline("000001", "day", 5)
        assert len(klines) > 0
        k = klines[0]
        assert "date" in k
        assert "open" in k
        assert "close" in k
        assert k["open"] > 0

    async def test_get_fund_nav(self, provider):
        """测试基金净值"""
        nav = await provider.get_fund_nav("016874")
        assert nav["nav"] > 0
        assert nav["nav_date"] != ""
        assert nav["source"] == "eastmoney"

    async def test_get_realtime_empty(self, provider):
        """测试空列表"""
        result = await provider.get_realtime_quote([])
        assert result == {}

    async def test_price_accuracy(self, provider):
        """测试价格精度（验证除法因子）"""
        result = await provider.get_realtime_quote(["000001", "510310"])
        # 股票价格应该在合理范围内
        if "000001" in result:
            assert 1 < result["000001"]["price"] < 100
        # ETF 价格应该在合理范围内
        if "510310" in result:
            assert 1 < result["510310"]["price"] < 100
