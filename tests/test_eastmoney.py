"""东方财富数据源测试"""
import pytest
import asyncio
from praxis.engine.data.eastmoney import (
    EastMoneyDataProvider,
    _detect_market,
    _to_eastmoney_secid,
    _is_fund,
)


class TestTickerConversion:
    """Ticker 格式转换测试"""

    def test_detect_market_sh_stock(self):
        assert _detect_market("STOCK_A") == 1

    def test_detect_market_sh_etf(self):
        assert _detect_market("ETF_300") == 1
        assert _detect_market("ETF_500") == 1

    def test_detect_market_sz_stock(self):
        assert _detect_market("000001") == 0
        assert _detect_market("300750") == 0

    def test_detect_market_sz_etf(self):
        assert _detect_market("159915") == 0

    def test_detect_market_fund(self):
        assert _detect_market("FUND_A") == 0
        assert _detect_market("161725") == 0

    def test_to_secid_sh(self):
        assert _to_eastmoney_secid("STOCK_A") == "1.STOCK_A"
        assert _to_eastmoney_secid("ETF_300") == "1.ETF_300"

    def test_to_secid_sz(self):
        assert _to_eastmoney_secid("000001") == "0.000001"
        assert _to_eastmoney_secid("159915") == "0.159915"

    def test_to_secid_already_formatted(self):
        assert _to_eastmoney_secid("1.STOCK_A") == "1.STOCK_A"

    def test_is_fund(self):
        assert _is_fund("FUND_A") is True
        assert _is_fund("161725") is True
        assert _is_fund("STOCK_A") is False
        assert _is_fund("ETF_300") is False


class TestEastMoneyDataProvider:
    """东方财富数据源集成测试"""

    @pytest.fixture
    def provider(self):
        p = EastMoneyDataProvider()
        yield p
        asyncio.get_event_loop().run_until_complete(p.close())

    def test_get_realtime_stock(self, provider):
        """测试股票实时行情"""
        result = asyncio.get_event_loop().run_until_complete(
            provider.get_realtime_quote(["STOCK_A"])
        )
        assert "STOCK_A" in result
        q = result["STOCK_A"]
        assert q["price"] > 0
        assert q["name"] != ""
        assert q["source"] == "eastmoney"

    def test_get_realtime_etf(self, provider):
        """测试 ETF 实时行情"""
        result = asyncio.get_event_loop().run_until_complete(
            provider.get_realtime_quote(["ETF_300"])
        )
        assert "ETF_300" in result
        q = result["ETF_300"]
        assert q["price"] > 0
        assert q["price"] < 100  # ETF 价格通常 < 100

    def test_get_realtime_fund(self, provider):
        """测试场外基金净值"""
        result = asyncio.get_event_loop().run_until_complete(
            provider.get_realtime_quote(["FUND_A"])
        )
        assert "FUND_A" in result
        q = result["FUND_A"]
        assert q["price"] > 0

    def test_get_realtime_batch(self, provider):
        """测试批量查询"""
        result = asyncio.get_event_loop().run_until_complete(
            provider.get_realtime_quote(["STOCK_A", "ETF_300"])
        )
        assert len(result) >= 1  # 至少一个成功

    def test_get_history_kline(self, provider):
        """测试历史K线"""
        klines = asyncio.get_event_loop().run_until_complete(
            provider.get_history_kline("STOCK_A", "day", 5)
        )
        assert len(klines) > 0
        k = klines[0]
        assert "date" in k
        assert "open" in k
        assert "close" in k
        assert k["open"] > 0

    def test_get_fund_nav(self, provider):
        """测试基金净值"""
        nav = asyncio.get_event_loop().run_until_complete(
            provider.get_fund_nav("FUND_A")
        )
        assert nav["nav"] > 0
        assert nav["nav_date"] != ""
        assert nav["source"] == "eastmoney"

    def test_get_realtime_empty(self, provider):
        """测试空列表"""
        result = asyncio.get_event_loop().run_until_complete(
            provider.get_realtime_quote([])
        )
        assert result == {}

    def test_price_accuracy(self, provider):
        """测试价格精度（验证除法因子）"""
        result = asyncio.get_event_loop().run_until_complete(
            provider.get_realtime_quote(["STOCK_A", "ETF_300"])
        )
        # 股票价格应该在合理范围内
        if "STOCK_A" in result:
            assert 1 < result["STOCK_A"]["price"] < 100
        # ETF 价格应该在合理范围内
        if "ETF_300" in result:
            assert 1 < result["ETF_300"]["price"] < 100
