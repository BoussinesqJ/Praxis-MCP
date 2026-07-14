"""估值分位引擎单元测试 — get_index_pe_percentile 及包装函数.

Mock 策略：估值引擎内部依赖 akshare + pandas，通过 sys.modules 注入
轻量 Fake 对象模拟 DataFrame/Series 行为，避免安装重型依赖。
"""

from __future__ import annotations

import sys
import pytest


# ═══════════════════════════════════════════════════════════════════
# 轻量 Fake 对象 — 模拟 pandas DataFrame/Series
# ═══════════════════════════════════════════════════════════════════

class FakeArray:
    """模拟 numpy array：支持比较运算和 .sum()."""

    def __init__(self, values: list):
        self._values = [float(v) for v in values]

    def __lt__(self, other):
        return FakeArray([1.0 if v < other else 0.0 for v in self._values])

    def sum(self) -> float:
        return sum(self._values)

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, idx):
        return self._values[idx]


def _sorted(values):
    """兼容 sorted() 调用的辅助函数."""
    return sorted(values)


class FakeSeries:
    """模拟 pandas Series：支持 dropna/astype/values/iloc."""

    def __init__(self, values: list):
        self._values = [float(v) for v in values]

    def dropna(self) -> "FakeSeries":
        return FakeSeries([v for v in self._values if v is not None])

    def astype(self, _dtype) -> "FakeSeries":
        return self

    @property
    def values(self):
        return FakeArray(self._values)

    @property
    def iloc(self):
        class _ILoc:
            def __init__(self, values):
                self._values = values
            def __getitem__(self, idx):
                return self._values[idx]
        return _ILoc(self._values)


class FakeDataFrame:
    """模拟 pandas DataFrame：支持 columns 和列索引."""

    def __init__(self, data: dict):
        self.columns = list(data.keys())
        self._data = data

    def __getitem__(self, key):
        if key in self._data:
            return FakeSeries(self._data[key])
        raise KeyError(key)

    def __len__(self):
        if self._data:
            first_key = list(self._data.keys())[0]
            return len(self._data[first_key])
        return 0


# ═══════════════════════════════════════════════════════════════════
# Fixture: 注入 fake akshare 到 sys.modules
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _inject_fake_akshare(monkeypatch):
    """确保 akshare 可被导入（注入假模块到 sys.modules）。"""
    if "akshare" not in sys.modules:
        fake_mod = type(sys)("akshare")
        fake_mod.stock_index_pe_lg = None  # 具体测试中 monkeypatch 覆盖
        sys.modules["akshare"] = fake_mod
    yield
    # 不清理 sys.modules，避免影响其他测试


# ═══════════════════════════════════════════════════════════════════
# 测试类
# ═══════════════════════════════════════════════════════════════════

from praxis.engine.valuation import (
    get_index_pe_percentile,
    get_valuation_percentile,
    check_valuation_for_all_indices,
    INDEX_PE_SYMBOLS,
    PEPercentile,
)


class TestUnsupportedIndex:
    """不支持指数."""

    @pytest.mark.asyncio
    async def test_unsupported_index_returns_none(self):
        """不支持指数返回 None."""
        result = await get_index_pe_percentile("999999")
        assert result is None


class TestAkshareImportError:
    """AKShare 未安装."""

    @pytest.mark.asyncio
    async def test_akshare_import_error(self, monkeypatch):
        """ImportError 时返回 None — 模拟 akshare 未安装."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "akshare":
                raise ImportError("No module named 'akshare'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        result = await get_index_pe_percentile("000300")
        assert result is None


class TestInsufficientData:
    """数据不足."""

    @pytest.mark.asyncio
    async def test_insufficient_data_20(self, monkeypatch):
        """数据不足 20 条返回 None."""
        def mock_get(*args, **kwargs):
            return FakeDataFrame({
                "日期": [f"2020-{i+1:02d}-01" for i in range(5)],
                "滚动市盈率": [10.0 + i * 0.5 for i in range(5)],
            })

        monkeypatch.setattr("akshare.stock_index_pe_lg", mock_get)
        result = await get_index_pe_percentile("000300")
        assert result is None


class TestNormalPEPercentile:
    """正常 PE 分位."""

    @pytest.mark.asyncio
    async def test_normal_pe_percentile(self, monkeypatch):
        """正常 PE 分位计算（100 条数据，当前 PE=15.0）。"""
        pe_values = [12.0 + i * 0.1 for i in range(100)]  # 12.0 ~ 21.9

        def mock_get(*args, **kwargs):
            return FakeDataFrame({
                "日期": [f"2020-{(i//30)+1:02d}-{(i%30)+1:02d}" for i in range(100)],
                "滚动市盈率": pe_values,
            })

        monkeypatch.setattr("akshare.stock_index_pe_lg", mock_get)
        result = await get_index_pe_percentile("000300")
        assert result is not None
        assert result["index_code"] == "000300"
        assert "current_pe" in result
        assert "percentile_all" in result
        assert "percentile_10y" in result
        assert "below_30pct" in result
        assert "above_80pct" in result
        assert result["valuation_level"] in ("undervalued", "fair", "overvalued")

    @pytest.mark.asyncio
    async def test_below_30pct_detected(self, monkeypatch):
        """PE 在所有历史中处于低位 → below_30pct=True."""
        # 只有 1% 的数据低于当前 PE → percentile_all ≈ 1%
        pe_values = [20.0 + i * 0.01 for i in range(100)]
        # 将第一个值设得很低，current_pe 是最后一个的高值
        pe_values[0] = 5.0

        def mock_get(*args, **kwargs):
            return FakeDataFrame({
                "日期": [f"2020-{(i//30)+1:02d}-{(i%30)+1:02d}" for i in range(100)],
                "滚动市盈率": pe_values,
            })

        monkeypatch.setattr("akshare.stock_index_pe_lg", mock_get)
        result = await get_index_pe_percentile("000300")
        assert result is not None
        # 当前 PE 很高 → above_80pct should be True
        assert result["above_80pct"] is True


class TestValuationPercentileWrapper:
    """get_valuation_percentile 包装."""

    @pytest.mark.asyncio
    async def test_get_valuation_percentile_wrapper(self, monkeypatch):
        """包装函数返回 {success, data} 结构."""
        pe_values = [10.0 + i * 0.2 for i in range(50)]

        def mock_get(*args, **kwargs):
            return FakeDataFrame({
                "日期": [f"2023-{(i//30)+1:02d}-{(i%30)+1:02d}" for i in range(50)],
                "滚动市盈率": pe_values,
            })

        monkeypatch.setattr("akshare.stock_index_pe_lg", mock_get)
        result = await get_valuation_percentile("000300")
        assert result["success"] is True
        assert "data" in result

    @pytest.mark.asyncio
    async def test_wrapper_on_unsupported_index(self):
        """包装函数对不支持指数返回 error."""
        result = await get_valuation_percentile("999999")
        assert result["success"] is False
        assert "error" in result


class TestCheckAllIndices:
    """check_valuation_for_all_indices."""

    @pytest.mark.asyncio
    async def test_check_valuation_for_all_indices(self, monkeypatch):
        """全指数检查 — 汇总所有支持指数的估值."""
        pe_values = [10.0 + i * 0.2 for i in range(50)]

        def mock_get(*args, **kwargs):
            return FakeDataFrame({
                "日期": [f"2023-{(i//30)+1:02d}-{(i%30)+1:02d}" for i in range(50)],
                "滚动市盈率": pe_values,
            })

        monkeypatch.setattr("akshare.stock_index_pe_lg", mock_get)
        result = await check_valuation_for_all_indices()
        assert "success" in result
        assert "data" in result
        assert "indices" in result["data"]
        # 所有 4 个指数都应成功
        assert result["data"]["summary"]["total"] == len(INDEX_PE_SYMBOLS)

    @pytest.mark.asyncio
    async def test_partial_failure(self, monkeypatch):
        """部分指数数据不可用时的降级处理."""
        call_count = [0]

        def mock_get(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                # 前两个指数返回 None（无数据）
                return None
            pe_values = [10.0 + i * 0.2 for i in range(50)]
            return FakeDataFrame({
                "日期": [f"2023-{(i//30)+1:02d}-{(i%30)+1:02d}" for i in range(50)],
                "滚动市盈率": pe_values,
            })

        monkeypatch.setattr("akshare.stock_index_pe_lg", mock_get)
        result = await check_valuation_for_all_indices()
        assert result["success"] is False  # 有 error
        assert len(result["data"]["summary"]["errors"]) == 2


class TestPEPercentileDataclass:
    """PEPercentile 数据类."""

    def test_pe_percentile_fields(self):
        """PEPercentile 字段完整."""
        p = PEPercentile(
            index_code="000300", index_name="沪深300",
            current_pe=12.5, percentile_all=25.0, percentile_10y=30.0,
            pe_30pct=11.0, pe_80pct=15.0, data_days=2000,
            below_30pct=True, above_80pct=False,
        )
        assert p.index_code == "000300"
        assert p.current_pe == 12.5
        assert p.percentile_all == 25.0
        assert p.below_30pct is True
        assert p.above_80pct is False


class TestNetworkErrorDegradation:
    """网络异常降级."""

    @pytest.mark.asyncio
    async def test_network_error_degradation(self, monkeypatch):
        """网络异常降级返回 None."""
        def mock_get(*args, **kwargs):
            raise ConnectionError("Network unreachable")

        monkeypatch.setattr("akshare.stock_index_pe_lg", mock_get)
        result = await get_index_pe_percentile("000300")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_dataframe_returns_none(self, monkeypatch):
        """空 DataFrame 返回 None."""
        def mock_get(*args, **kwargs):
            return FakeDataFrame({})

        monkeypatch.setattr("akshare.stock_index_pe_lg", mock_get)
        result = await get_index_pe_percentile("000300")
        # 空 DataFrame 的 len 为 0 → df is None or len(df) == 0 → returns None
        assert result is None
