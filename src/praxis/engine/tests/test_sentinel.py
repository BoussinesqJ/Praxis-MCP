"""哨兵雷达引擎单元测试 — SentinelEngine + 工具函数."""

from __future__ import annotations

import pytest

from praxis.engine.sentinel import (
    SentinelEngine,
    _compute_ma,
    _compute_vol_ratio,
    _classify_vol,
    SENTINEL_DEFINITIONS,
    SENTINEL_ORDER,
)


class TestSentinelDefaultInit:
    """默认初始化."""

    def test_default_init_8_etf(self, tmp_path):
        """默认初始化含 8 个 ETF 哨兵."""
        engine = SentinelEngine(workspace=str(tmp_path))
        assert len(engine._sentinel_order) == 8
        assert engine._sentinel_order == SENTINEL_ORDER
        assert len(engine._sentinel_defs) == 8
        assert "510300" in engine._sentinel_defs

    def test_config_loader_override(self, tmp_path, fake_config_loader):
        """config_loader 覆盖哨兵定义."""
        engine = SentinelEngine(
            workspace=str(tmp_path),
            config_loader=fake_config_loader,
            investor_id="inv-test",
            portfolio_id="core",
        )
        assert len(engine._sentinel_order) == 2
        assert engine._sentinel_order == ["510300", "159915"]


class TestComputeMA:
    """_compute_ma 工具函数."""

    def test_compute_ma_normal(self):
        """正常 MA 计算."""
        closes = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0]
        ma5 = _compute_ma(closes, 5)
        assert ma5 == pytest.approx((16 + 17 + 18 + 19 + 20) / 5, rel=1e-6)

    def test_compute_ma_insufficient_data(self):
        """数据不足时使用全部数据."""
        closes = [10.0, 11.0, 12.0]
        ma10 = _compute_ma(closes, 10)
        assert ma10 == pytest.approx(11.0, rel=1e-6)


class TestComputeVolRatio:
    """_compute_vol_ratio 工具函数."""

    def test_compute_vol_ratio_normal(self):
        """正常量比计算 — 最近5日均量 vs 前一日."""
        volumes = [100, 100, 100, 100, 100, 200]
        ratio = _compute_vol_ratio(volumes)
        assert ratio == pytest.approx(2.0, rel=1e-6)

    def test_compute_vol_ratio_insufficient(self):
        """不足6条数据返回默认值."""
        volumes = [100, 200, 300]
        ratio = _compute_vol_ratio(volumes)
        assert ratio == 1.0


class TestClassifyVol:
    """_classify_vol 工具函数."""

    def test_classify_vol_high(self):
        """异常放量 > 1.5."""
        desc = _classify_vol(2.0)
        assert "异常放量" in desc

    def test_classify_vol_low(self):
        """静默缩量 < 0.6."""
        desc = _classify_vol(0.4)
        assert "静默缩量" in desc

    def test_classify_vol_normal(self):
        """量平 0.6~1.5."""
        desc = _classify_vol(1.0)
        assert "量平" in desc


class TestSentinelScan:
    """scan 集成测试（需要 mock K线获取）."""

    @pytest.mark.asyncio
    async def test_scan_with_mocked_kline(self, tmp_path, monkeypatch):
        """使用 monkeypatch 模拟 scan 获取 K 线."""
        async def fake_fetch(ticker, count=70):
            klines = []
            for i in range(count):
                klines.append({
                    "date": f"2024-01-{(i%28)+1:02d}",
                    "open": 2.0, "high": 2.2, "low": 1.9,
                    "close": 2.0 + i * 0.01, "volume": 1e7 + i * 1e5,
                })
            return klines

        monkeypatch.setattr("praxis.engine.sentinel._fetch_kline", fake_fetch)

        engine = SentinelEngine(workspace=str(tmp_path))
        result = await engine.scan()
        assert "bullish_count" in result
        assert "total" in result
        assert "state" in result
        assert "position_limit_pct" in result

    def test_rule23_trigger(self, tmp_path):
        """Rule23 情绪起爆器 — 需要连续2次>=4触发."""
        engine = SentinelEngine(workspace=str(tmp_path))
        # 模拟：无历史
        status = engine.get_rule23_status()
        assert not status["triggered"]

    def test_position_tiers_default(self, tmp_path):
        """仓位阶梯 — 默认 0-2→防御, 3-5→试探, 6-8→进攻."""
        engine = SentinelEngine(workspace=str(tmp_path))
        tiers = engine.POSITION_TIERS
        assert tiers[0] == (2, "绝对防守期", 10.0)
        assert tiers[1] == (4, "适度试探期", 20.0)
        assert tiers[2] == (6, "积极配置期", 30.0)
        assert tiers[3] == (8, "全面进攻期", 50.0)
