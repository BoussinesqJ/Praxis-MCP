"""E2E 降级链测试 — 多数据源容错 + 缓存兜底

场景：
1. 主 Provider(Tencent) 失败 → 自动回退备用 Provider
2. 所有 Provider 失败 → 降级到内存缓存
3. 验证：最终有数据返回，无崩溃
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from praxis.engine.data.registry import ProviderRegistry, FAILURE_THRESHOLD
from praxis.engine.data.provider import CachedDataProvider
from praxis.core.interfaces import DataProvider
from praxis.engine.tests.conftest import FakeDataProvider


class _AlwaysFailProvider(DataProvider):
    """模拟永远失败的主数据源（Tencent 不可用）"""

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        raise ConnectionError("Tencent 数据源不可用")

    async def get_history_kline(self, ticker: str, period: str = "day", count: int = 60) -> list[dict]:
        raise ConnectionError("Tencent K线不可用")

    async def get_fund_nav(self, ticker: str) -> dict:
        raise ConnectionError("Tencent 净值不可用")


class _PartialProvider(DataProvider):
    """模拟部分可用的备用数据源"""

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        return {t: {"price": 50.0, "name": f"PB-{t}", "source": "partial"} for t in tickers}

    async def get_history_kline(self, ticker: str, period: str = "day", count: int = 60) -> list[dict]:
        return [{"date": "2026-07-01", "open": 50.0, "high": 52.0, "low": 48.0, "close": 51.0, "volume": 1000}]

    async def get_fund_nav(self, ticker: str) -> dict:
        return {"nav": 1.5, "nav_date": "2026-07-01"}


class _AllFailProvider(DataProvider):
    """模拟所有数据源都失败"""

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        raise RuntimeError("所有数据源不可用")

    async def get_history_kline(self, ticker: str, period: str = "day", count: int = 60) -> list[dict]:
        raise RuntimeError("所有数据源不可用")

    async def get_fund_nav(self, ticker: str) -> dict:
        raise RuntimeError("所有数据源不可用")


@pytest.mark.asyncio
async def test_e2e_fallback_chain_main_fails_fallback_succeeds():
    """主 Provider 失败 → 备用 Provider 成功 → 返回数据

    验证：降级链正常工作，最终有数据返回
    """
    registry = ProviderRegistry()

    # 注册：primary 优先但会失败，fallback 次之
    registry.register("tencent", _AlwaysFailProvider, priority=1)
    registry.register("mootdx", _PartialProvider, priority=5)

    chain = registry.get_chain()
    assert len(chain) >= 1, "至少应有 1 个可用数据源"

    # 模拟逐步降级调用
    merged: dict[str, dict] = {}
    remaining = ["000001", "600519"]

    for name, provider in chain:
        if not remaining:
            break
        try:
            result = await provider.get_realtime_quote(remaining)
            if result:
                registry.report_success(name)
                merged.update(result)
                remaining = [t for t in remaining if t not in result]
        except Exception:
            registry.report_failure(name)

    # 验证 primary 失败、fallback 成功
    assert len(merged) >= 2, f"应有数据返回: {merged}"
    assert "000001" in merged, "000001 应有数据"
    assert "600519" in merged, "600519 应有数据"
    assert merged["000001"].get("source") == "partial", "数据应来自备用源"

    # 验证 primary 健康状态变为 unhealthy
    status = registry.get_status("tencent")
    assert status is not None
    assert not status["healthy"] or status["failure_count"] > 0, (
        f"primary 应记录失败: {status}"
    )

    # 验证 fallback 健康
    mootdx_status = registry.get_status("mootdx")
    assert mootdx_status is not None
    assert mootdx_status["healthy"], "fallback 应为健康"


@pytest.mark.asyncio
async def test_e2e_fallback_chain_all_fail_cache_fallback():
    """所有 Provider 失败 → 降级到缓存 → 最终有数据返回

    验证：无任何 Provider 可用时，现有缓存被返回，无崩溃
    """
    # 构造 CachedDataProvider，禁用自动发现，手动注册 AllFail
    provider = CachedDataProvider(auto_discover=False)
    provider._registry.register("doomed", _AllFailProvider, priority=1)

    # 预热缓存：直接写入内存缓存
    provider._memory_cache["000001"] = {
        "price": 12.5, "name": "平安银行(缓存)", "is_stale": False,
    }
    provider._memory_cache["600519"] = {
        "price": 1850.0, "name": "贵州茅台(缓存)", "is_stale": False,
    }

    # 调用 get_realtime_quote — 所有源失败后应降级缓存
    result = await provider.get_realtime_quote(["000001", "600519"])

    assert result, "即使所有 Provider 失败，缓存应返回数据"
    assert "000001" in result, "000001 应从缓存返回"
    assert "600519" in result, "600519 应从缓存返回"
    assert result["000001"]["name"] == "平安银行(缓存)", "数据来源应为缓存"

    # 验证数据来源应为缓存
    assert result["000001"]["name"] == "平安银行(缓存)", "数据来源应为缓存"

    # 验证数据可使用（即使 is_stale 可能为 True）

    await provider.close()
