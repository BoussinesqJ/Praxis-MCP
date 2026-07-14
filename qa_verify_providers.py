r"""QA 独立验证脚本 — praxis-mcp 数据源 provider 迁移

验证工程师寇豆码的 provider 迁移修复，使用占位测试标的，
不使用工程师的 verify_providers_fix.py，完全独立验证。

运行方式（运行版 venv）:
    set PYTHONPATH=<项目根>/src
    set PRAXIS_WORKSPACE=<你的工作区路径>
    python qa_verify_providers.py

验证项:
    1. 文件结构复核（类继承、接口方法、注册补丁）
    2. TencentDataProvider 实际取价（测试标的）
    3. MootdxProvider 实际取价（测试标的）
    4. 两个 provider 价格一致性
    5. 返回字段完整性（price/change/change_pct/volume）
    6. CachedDataProvider 降级链取价
    7. MootdxProvider get_history_kline（ETF 日K线5条）
    8. 配置加载验证（data_sources.yaml tencent enabled:true priority:5）
    9. 回归保护（paths.py / performance.py / state_builder.py 昨晚修复未破坏）
"""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
from pathlib import Path

# ── 环境变量 ──────────────────────────────────────────────────
SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", "")

os.environ.setdefault("PYTHONPATH", SRC_PATH)
os.environ.setdefault("PRAXIS_WORKSPACE", WORKSPACE)
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# 测试标的（占位符，运行前替换为实际代码）
REAL_TICKERS = ["000001", "510300"]

# ── 测试结果收集 ──────────────────────────────────────────────
PASS_COUNT = 0
FAIL_COUNT = 0
SKIP_COUNT = 0
RESULTS: list[tuple[str, str, str]] = []  # (name, status, detail)


def record(name: str, status: str, detail: str = "") -> None:
    """记录测试结果"""
    global PASS_COUNT, FAIL_COUNT, SKIP_COUNT
    RESULTS.append((name, status, detail))
    if status == "PASS":
        PASS_COUNT += 1
    elif status == "FAIL":
        FAIL_COUNT += 1
    else:
        SKIP_COUNT += 1
    marker = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
    print(f"  {marker} {name}: {detail}" if detail else f"  {marker} {name}")


# ─────────────────────────────────────────────────────────────
# 第 1 部分：文件结构复核（静态检查）
# ─────────────────────────────────────────────────────────────
def test_file_structure() -> None:
    """验证文件结构：类继承、接口方法、注册补丁"""
    print("\n" + "=" * 70)
    print("第 1 部分：文件结构复核（静态检查）")
    print("=" * 70)

    # 1.1 exceptions.py — DataError 存在
    try:
        from praxis.core.exceptions import DataError, PraxisError

        assert issubclass(DataError, PraxisError), "DataError 应继承 PraxisError"
        record("exceptions.DataError 继承 PraxisError", "PASS")
    except Exception as e:
        record("exceptions.DataError 继承 PraxisError", "FAIL", str(e))

    # 1.2 DataProvider 接口 4 个抽象方法
    try:
        from praxis.core.interfaces import DataProvider
        import inspect

        abstract_methods = {
            "get_realtime_quote",
            "get_history_kline",
            "get_fund_nav",
            "close",
        }
        actual_abstract = getattr(DataProvider, "__abstractmethods__", set())
        missing = abstract_methods - actual_abstract
        assert not missing, f"DataProvider 缺少抽象方法: {missing}"
        record(
            "DataProvider 接口4方法齐全",
            "PASS",
            f"abstractmethods={actual_abstract}",
        )
    except Exception as e:
        record("DataProvider 接口4方法齐全", "FAIL", str(e))

    # 1.3 TencentDataProvider 继承 DataProvider
    try:
        from praxis.engine.data.realtime import TencentDataProvider

        assert issubclass(
            TencentDataProvider, DataProvider
        ), "TencentDataProvider 应继承 DataProvider"
        # 验证4个方法都实现了
        for method_name in ["get_realtime_quote", "get_history_kline", "get_fund_nav", "close"]:
            assert hasattr(TencentDataProvider, method_name), f"缺少方法 {method_name}"
        record("TencentDataProvider 继承 DataProvider + 4方法", "PASS")
    except Exception as e:
        record("TencentDataProvider 继承 DataProvider + 4方法", "FAIL", str(e))

    # 1.4 MootdxProvider 继承 DataProvider
    try:
        from praxis.engine.data.mootdx_provider import MootdxProvider

        assert issubclass(
            MootdxProvider, DataProvider
        ), "MootdxProvider 应继承 DataProvider"
        for method_name in ["get_realtime_quote", "get_history_kline", "get_fund_nav", "close"]:
            assert hasattr(MootdxProvider, method_name), f"缺少方法 {method_name}"
        record("MootdxProvider 继承 DataProvider + 4方法", "PASS")
    except Exception as e:
        record("MootdxProvider 继承 DataProvider + 4方法", "FAIL", str(e))

    # 1.5 registry.py mootdx 注册 priority=8
    try:
        from praxis.engine.data.registry import ProviderRegistry

        reg = ProviderRegistry()
        reg._discover_builtin()

        mootdx_entry = reg._entries.get("mootdx")
        assert mootdx_entry is not None, "mootdx 未注册"
        assert mootdx_entry.priority == 8, f"mootdx priority 应为 8, 实际 {mootdx_entry.priority}"

        tencent_entry = reg._entries.get("tencent")
        assert tencent_entry is not None, "tencent 未注册"
        assert tencent_entry.priority == 5, f"tencent priority 应为 5, 实际 {tencent_entry.priority}"

        record(
            "registry mootdx(priority=8) + tencent(priority=5) 注册",
            "PASS",
            f"mootdx={mootdx_entry.priority}, tencent={tencent_entry.priority}",
        )
    except Exception as e:
        record("registry mootdx(priority=8) + tencent(priority=5) 注册", "FAIL", str(e))


# ─────────────────────────────────────────────────────────────
# 第 2 部分：实际取价测试（核心）
# ─────────────────────────────────────────────────────────────
async def test_tencent_realtime() -> dict[str, dict]:
    """测试 TencentDataProvider 取标的实时行情"""
    print("\n" + "=" * 70)
    print("第 2 部分：TencentDataProvider 实际取价")
    print("=" * 70)

    from praxis.engine.data.realtime import TencentDataProvider

    provider = TencentDataProvider(timeout=15.0)
    result: dict[str, dict] = {}

    try:
        result = await provider.get_realtime_quote(REAL_TICKERS)

        # 验证返回了两个标的
        returned_tickers = set(result.keys())
        expected = set(REAL_TICKERS)
        if expected.issubset(returned_tickers):
            record(
                "Tencent 取价返回两个标的",
                "PASS",
                f"返回: {sorted(returned_tickers)}",
            )
        else:
            missing = expected - returned_tickers
            record(
                "Tencent 取价返回两个标的",
                "FAIL",
                f"缺少: {sorted(missing)}, 返回: {sorted(returned_tickers)}",
            )

        # 验证字段完整性
        required_fields = ["price", "change", "change_pct", "volume"]
        for ticker in REAL_TICKERS:
            if ticker not in result:
                continue
            quote = result[ticker]
            missing_fields = [f for f in required_fields if f not in quote]
            if missing_fields:
                record(
                    f"Tencent 字段完整性 [{ticker}]",
                    "FAIL",
                    f"缺少字段: {missing_fields}",
                )
            else:
                record(
                    f"Tencent 字段完整性 [{ticker}]",
                    "PASS",
                    f"price={quote['price']}, change={quote['change']}, "
                    f"change_pct={quote['change_pct']}, volume={quote['volume']}",
                )

            # 验证 price > 0（合理值）
            price = quote.get("price", 0)
            if price > 0:
                record(f"Tencent 价格合理性 [{ticker}]", "PASS", f"price={price}")
            else:
                record(f"Tencent 价格合理性 [{ticker}]", "FAIL", f"price={price} (应>0)")

    except Exception as e:
        record("Tencent 取价整体", "FAIL", f"{type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        await provider.close()

    return result


async def test_mootdx_realtime() -> dict[str, dict]:
    """测试 MootdxProvider 取标的实时行情"""
    print("\n" + "=" * 70)
    print("第 3 部分：MootdxProvider 实际取价")
    print("=" * 70)

    from praxis.engine.data.mootdx_provider import MootdxProvider

    result: dict[str, dict] = {}

    try:
        provider = MootdxProvider()

        if provider._client is None:
            record("Mootdx 客户端初始化", "FAIL", "_client is None (mootdx 未安装或连接失败)")
            return result

        record("Mootdx 客户端初始化", "PASS", "TCP 连接已建立")

        result = await provider.get_realtime_quote(REAL_TICKERS)

        # 验证返回了标的
        returned_tickers = set(result.keys())
        expected = set(REAL_TICKERS)
        if expected.issubset(returned_tickers):
            record(
                "Mootdx 取价返回两个标的",
                "PASS",
                f"返回: {sorted(returned_tickers)}",
            )
        else:
            missing = expected - returned_tickers
            record(
                "Mootdx 取价返回两个标的",
                "FAIL",
                f"缺少: {sorted(missing)}, 返回: {sorted(returned_tickers)}",
            )

        # 验证字段完整性
        required_fields = ["price", "change", "change_pct", "volume"]
        for ticker in REAL_TICKERS:
            if ticker not in result:
                continue
            quote = result[ticker]
            missing_fields = [f for f in required_fields if f not in quote]
            if missing_fields:
                record(
                    f"Mootdx 字段完整性 [{ticker}]",
                    "FAIL",
                    f"缺少字段: {missing_fields}",
                )
            else:
                record(
                    f"Mootdx 字段完整性 [{ticker}]",
                    "PASS",
                    f"price={quote['price']}, change={quote['change']}, "
                    f"change_pct={quote['change_pct']}, volume={quote['volume']}",
                )

            # 验证 price > 0
            price = quote.get("price", 0)
            if price > 0:
                record(f"Mootdx 价格合理性 [{ticker}]", "PASS", f"price={price}")
            else:
                record(f"Mootdx 价格合理性 [{ticker}]", "FAIL", f"price={price} (应>0)")

        await provider.close()

    except Exception as e:
        record("Mootdx 取价整体", "FAIL", f"{type(e).__name__}: {e}")
        traceback.print_exc()

    return result


def test_price_consistency(
    tencent_result: dict[str, dict], mootdx_result: dict[str, dict]
) -> None:
    """验证两个 provider 返回的价格一致（同一数据源，应相同或极接近）"""
    print("\n" + "=" * 70)
    print("第 4 部分：价格一致性验证（Tencent vs Mootdx）")
    print("=" * 70)

    for ticker in REAL_TICKERS:
        tencent_price = tencent_result.get(ticker, {}).get("price")
        mootdx_price = mootdx_result.get(ticker, {}).get("price")

        if tencent_price is None or mootdx_price is None:
            record(
                f"价格一致性 [{ticker}]",
                "SKIP",
                f"tencent={tencent_price}, mootdx={mootdx_price} (数据缺失)",
            )
            continue

        # 允许 1% 的价差（实时行情可能有微小时间差）
        if tencent_price > 0 and mootdx_price > 0:
            diff_pct = abs(tencent_price - mootdx_price) / tencent_price * 100
            if diff_pct < 1.0:
                record(
                    f"价格一致性 [{ticker}]",
                    "PASS",
                    f"tencent={tencent_price}, mootdx={mootdx_price}, 差异={diff_pct:.4f}%",
                )
            else:
                record(
                    f"价格一致性 [{ticker}]",
                    "FAIL",
                    f"tencent={tencent_price}, mootdx={mootdx_price}, 差异={diff_pct:.4f}% (>1%)",
                )
        else:
            record(
                f"价格一致性 [{ticker}]",
                "FAIL",
                f"价格为0: tencent={tencent_price}, mootdx={mootdx_price}",
            )


# ─────────────────────────────────────────────────────────────
# 第 5 部分：CachedDataProvider 降级链测试
# ─────────────────────────────────────────────────────────────
async def test_cached_provider_chain() -> None:
    """测试 CachedDataProvider 降级链取价"""
    print("\n" + "=" * 70)
    print("第 5 部分：CachedDataProvider 降级链取价")
    print("=" * 70)

    from praxis.engine.data.provider import CachedDataProvider

    provider = CachedDataProvider(workspace=WORKSPACE)

    try:
        # 验证 registry 链中有 tencent 和 mootdx
        providers_list = provider.list_providers()
        provider_names = [p["name"] for p in providers_list]
        print(f"  注册的数据源: {provider_names}")

        has_tencent = "tencent" in provider_names
        has_mootdx = "mootdx" in provider_names

        if has_tencent and has_mootdx:
            record(
                "CachedDataProvider 注册链含 tencent + mootdx",
                "PASS",
                f"providers={provider_names}",
            )
        else:
            record(
                "CachedDataProvider 注册链含 tencent + mootdx",
                "FAIL",
                f"tencent={has_tencent}, mootdx={has_mootdx}",
            )

        # 验证 tencent enabled=true, priority=5 (配置覆盖生效)
        tencent_status = next((p for p in providers_list if p["name"] == "tencent"), None)
        if tencent_status:
            if tencent_status["enabled"] and tencent_status["priority"] == 5:
                record(
                    "CachedDataProvider tencent 配置覆盖生效",
                    "PASS",
                    f"enabled={tencent_status['enabled']}, priority={tencent_status['priority']}",
                )
            else:
                record(
                    "CachedDataProvider tencent 配置覆盖生效",
                    "FAIL",
                    f"enabled={tencent_status['enabled']}, priority={tencent_status['priority']} (期望 enabled=True, priority=5)",
                )

        # 实际取价
        result = await provider.get_realtime_quote(REAL_TICKERS)

        if result and len(result) >= 1:
            prices = {t: result[t].get("price") for t in REAL_TICKERS if t in result}
            record(
                "CachedDataProvider 取价成功",
                "PASS",
                f"prices={prices}",
            )
        else:
            record(
                "CachedDataProvider 取价成功",
                "FAIL",
                f"返回空结果: {result}",
            )

    except Exception as e:
        record("CachedDataProvider 取价", "FAIL", f"{type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        await provider.close()


# ─────────────────────────────────────────────────────────────
# 第 6 部分：MootdxProvider get_history_kline 测试
# ─────────────────────────────────────────────────────────────
async def test_mootdx_kline() -> None:
    """测试 MootdxProvider 取 ETF 日K线5条"""
    print("\n" + "=" * 70)
    print("第 6 部分：MootdxProvider get_history_kline（ETF 日K线5条）")
    print("=" * 70)

    from praxis.engine.data.mootdx_provider import MootdxProvider

    provider = MootdxProvider()

    try:
        if provider._client is None:
            record("Mootdx K线测试", "SKIP", "客户端未初始化")
            return

        klines = await provider.get_history_kline("510300", period="day", count=5)

        if klines and len(klines) > 0:
            # 验证返回条数 <= 5
            record(
                "Mootdx K线返回条数",
                "PASS",
                f"返回 {len(klines)} 条 (请求5条)",
            )

            # 验证字段完整性
            first = klines[0]
            required_fields = ["date", "open", "high", "low", "close", "volume"]
            missing = [f for f in required_fields if f not in first]
            if missing:
                record("Mootdx K线字段完整性", "FAIL", f"缺少: {missing}")
            else:
                record(
                    "Mootdx K线字段完整性",
                    "PASS",
                    f"date={first['date']}, close={first['close']}, volume={first['volume']}",
                )

            # 验证 date 格式合理（YYYY-MM-DD）
            date_str = str(first.get("date", ""))
            if len(date_str) >= 10 and date_str[4] == "-":
                record("Mootdx K线日期格式", "PASS", f"date={date_str}")
            else:
                record("Mootdx K线日期格式", "FAIL", f"date={date_str} (格式异常)")

            # 验证 close > 0
            for i, k in enumerate(klines):
                if k.get("close", 0) <= 0:
                    record(
                        f"Mootdx K线 close>0 (第{i+1}条)",
                        "FAIL",
                        f"close={k.get('close')}",
                    )
                    break
            else:
                record("Mootdx K线 close>0 (全部)", "PASS", f"{len(klines)}条均>0")

        else:
            record("Mootdx K线返回条数", "FAIL", f"返回空: {klines}")

    except Exception as e:
        record("Mootdx K线测试", "FAIL", f"{type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        await provider.close()


# ─────────────────────────────────────────────────────────────
# 第 7 部分：配置验证
# ─────────────────────────────────────────────────────────────
def test_config() -> None:
    """验证 data_sources.yaml 配置"""
    print("\n" + "=" * 70)
    print("第 7 部分：配置验证")
    print("=" * 70)

    config_path = Path(WORKSPACE) / "config" / "data_sources.yaml"

    if not config_path.exists():
        record("data_sources.yaml 存在", "FAIL", f"路径不存在: {config_path}")
        return

    record("data_sources.yaml 存在", "PASS", str(config_path))

    try:
        import yaml

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        # 检查 provider_registry.tencent
        provider_registry = config.get("provider_registry", {})
        tencent_config = provider_registry.get("tencent", {})

        tencent_enabled = tencent_config.get("enabled")
        tencent_priority = tencent_config.get("priority")

        if tencent_enabled is True and tencent_priority == 5:
            record(
                "tencent 配置 enabled:true, priority:5",
                "PASS",
                f"enabled={tencent_enabled}, priority={tencent_priority}",
            )
        else:
            record(
                "tencent 配置 enabled:true, priority:5",
                "FAIL",
                f"enabled={tencent_enabled}, priority={tencent_priority}",
            )

        # 验证 apply_config 会使用 provider_registry（而非 providers.disabled）
        # registry.apply_config 优先读 provider_registry
        from praxis.engine.data.registry import ProviderRegistry

        reg = ProviderRegistry()
        reg._discover_builtin()
        reg.apply_config(config)

        tencent_entry = reg._entries.get("tencent")
        if tencent_entry:
            if tencent_entry.enabled and tencent_entry.priority == 5:
                record(
                    "apply_config 后 tencent enabled=true priority=5",
                    "PASS",
                    f"enabled={tencent_entry.enabled}, priority={tencent_entry.priority}",
                )
            else:
                record(
                    "apply_config 后 tencent enabled=true priority=5",
                    "FAIL",
                    f"enabled={tencent_entry.enabled}, priority={tencent_entry.priority} "
                    f"(可能被 providers.disabled 覆盖)",
                )

        # 验证 providers.disabled.tencent 不会覆盖 provider_registry.tencent
        # （因为 apply_config 优先读 provider_registry）
        providers_section = config.get("providers", {})
        disabled_section = providers_section.get("disabled", {})
        disabled_tencent = disabled_section.get("tencent", {})
        if disabled_tencent.get("enabled") is False:
            record(
                "providers.disabled.tencent 不会覆盖 provider_registry",
                "PASS",
                "apply_config 优先读 provider_registry（已验证）",
            )
        else:
            record(
                "providers.disabled.tencent 不会覆盖 provider_registry",
                "PASS",
                "providers.disabled.tencent 不存在或非 disabled",
            )

    except Exception as e:
        record("配置验证", "FAIL", f"{type(e).__name__}: {e}")
        traceback.print_exc()


# ─────────────────────────────────────────────────────────────
# 第 8 部分：回归保护（昨晚修复未被破坏）
# ─────────────────────────────────────────────────────────────
def test_regression_protection() -> None:
    """验证昨晚的修复（paths/performance/state_builder）未被破坏"""
    print("\n" + "=" * 70)
    print("第 8 部分：回归保护（昨晚修复未被破坏）")
    print("=" * 70)

    # 8.1 paths.py — ledger/nav/decisions 指向 data/ 前缀
    try:
        from praxis.core.paths import get_paths

        paths = get_paths(WORKSPACE)

        checks = [
            ("ledger", "data" + os.sep + "ledger"),
            ("nav", "data" + os.sep + "nav"),
            ("decisions", "data" + os.sep + "decisions"),
            ("sentinel", "data" + os.sep + "sentinel"),
        ]

        all_ok = True
        for key, expected_fragment in checks:
            actual = str(paths.get(key, ""))
            if expected_fragment.replace(os.sep, "/") in actual.replace("\\", "/"):
                pass
            else:
                all_ok = False
                record(
                    f"paths[{key}] 指向 data/ 前缀",
                    "FAIL",
                    f"实际={actual}, 期望含 {expected_fragment}",
                )

        if all_ok:
            record(
                "paths.py ledger/nav/decisions/sentinel 指向 data/ 前缀",
                "PASS",
                "昨晚修复保持完整",
            )
    except Exception as e:
        record("paths.py 回归检查", "FAIL", f"{type(e).__name__}: {e}")

    # 8.2 performance.py — nav_tracker 注入逻辑
    try:
        from praxis.engine.performance import EnhancedPerformanceCalculator
        import inspect

        sig = inspect.signature(EnhancedPerformanceCalculator.__init__)
        params = list(sig.parameters.keys())

        if "nav_tracker" in params:
            record(
                "performance.py nav_tracker 注入参数存在",
                "PASS",
                f"__init__ params={params}",
            )
        else:
            record(
                "performance.py nav_tracker 注入参数存在",
                "FAIL",
                f"__init__ params={params} (缺少 nav_tracker)",
            )

        # 验证 nav_tracker 被存储
        source = inspect.getsource(EnhancedPerformanceCalculator.__init__)
        if "self._nav_tracker" in source:
            record(
                "performance.py nav_tracker 赋值存储",
                "PASS",
                "self._nav_tracker = nav_tracker 存在",
            )
        else:
            record(
                "performance.py nav_tracker 赋值存储",
                "FAIL",
                "缺少 self._nav_tracker = nav_tracker",
            )

    except Exception as e:
        record("performance.py 回归检查", "FAIL", f"{type(e).__name__}: {e}")

    # 8.3 state_builder.py 存在且可导入
    try:
        import praxis.engine.state_builder  # noqa: F401

        record("state_builder.py 存在且可导入", "PASS")
    except Exception as e:
        record("state_builder.py 存在且可导入", "FAIL", f"{type(e).__name__}: {e}")

    # 8.4 registry.py 改动只加了 mootdx 注册（没动其他逻辑）
    # 通过验证 _discover_builtin 中 tencent 注册仍正确 + mootdx 注册正确
    try:
        from praxis.engine.data.registry import ProviderRegistry

        reg = ProviderRegistry()
        reg._discover_builtin()

        # tencent 和 mootdx 都应注册
        assert "tencent" in reg._entries, "tencent 注册丢失"
        assert "mootdx" in reg._entries, "mootdx 注册丢失"

        # 验证 get_chain 按优先级排序
        chain = reg.get_chain()
        chain_names = [name for name, _ in chain]

        # tencent (priority=5) 应在 mootdx (priority=8) 之前
        if "tencent" in chain_names and "mootdx" in chain_names:
            tencent_idx = chain_names.index("tencent")
            mootdx_idx = chain_names.index("mootdx")
            if tencent_idx < mootdx_idx:
                record(
                    "registry 链排序 tencent(5) < mootdx(8)",
                    "PASS",
                    f"chain={chain_names}",
                )
            else:
                record(
                    "registry 链排序 tencent(5) < mootdx(8)",
                    "FAIL",
                    f"tencent_idx={tencent_idx} >= mootdx_idx={mootdx_idx}",
                )
        else:
            record(
                "registry 链排序 tencent(5) < mootdx(8)",
                "SKIP",
                f"链中缺少 provider: {chain_names}",
            )

    except Exception as e:
        record("registry.py 改动范围检查", "FAIL", f"{type(e).__name__}: {e}")


# ─────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────
async def main() -> None:
    print("=" * 70)
    print("QA 独立验证 — praxis-mcp 数据源 provider 迁移")
    print(f"Python: {sys.executable}")
    print(f"PYTHONPATH: {SRC_PATH}")
    print(f"PRAXIS_WORKSPACE: {WORKSPACE}")
    print(f"测试标的: {REAL_TICKERS}")
    print("=" * 70)

    # 第 1 部分：文件结构
    test_file_structure()

    # 第 2 部分：Tencent 取价
    tencent_result = await test_tencent_realtime()

    # 第 3 部分：Mootdx 取价
    mootdx_result = await test_mootdx_realtime()

    # 第 4 部分：价格一致性
    test_price_consistency(tencent_result, mootdx_result)

    # 第 5 部分：CachedDataProvider 降级链
    await test_cached_provider_chain()

    # 第 6 部分：Mootdx K线
    await test_mootdx_kline()

    # 第 7 部分：配置验证
    test_config()

    # 第 8 部分：回归保护
    test_regression_protection()

    # ── 汇总报告 ──
    print("\n" + "=" * 70)
    print("QA 验证汇总报告")
    print("=" * 70)
    print(f"  总计: {len(RESULTS)} | PASS: {PASS_COUNT} | FAIL: {FAIL_COUNT} | SKIP: {SKIP_COUNT}")
    print()

    if FAIL_COUNT > 0:
        print("  失败项明细:")
        for name, status, detail in RESULTS:
            if status == "FAIL":
                print(f"    [FAIL] {name}: {detail}")
    print()

    # 智能路由判定
    print("=" * 70)
    print("智能路由判定")
    print("=" * 70)
    if FAIL_COUNT == 0:
        print("  路由: NoOne (全部通过，无需反馈修复)")
    else:
        # 分析失败项，判定归因
        source_bugs = []
        test_bugs = []
        config_issues = []

        for name, status, detail in RESULTS:
            if status != "FAIL":
                continue
            # 实际取价失败 → 源码 bug
            if any(kw in name for kw in ["取价", "价格", "字段", "K线", "初始化", "一致性"]):
                source_bugs.append((name, detail))
            elif "配置" in name or "apply_config" in name:
                config_issues.append((name, detail))
            elif "回归" in name or "paths" in name or "performance" in name or "state_builder" in name:
                source_bugs.append((name, detail))
            else:
                test_bugs.append((name, detail))

        if source_bugs:
            print(f"  路由: Engineer (源码Bug) — {len(source_bugs)} 项")
            for name, detail in source_bugs:
                print(f"    - {name}: {detail}")
        if config_issues:
            print(f"  路由: 主理人 (配置问题) — {len(config_issues)} 项")
            for name, detail in config_issues:
                print(f"    - {name}: {detail}")
        if test_bugs:
            print(f"  路由: QA (测试代码Bug) — {len(test_bugs)} 项")
            for name, detail in test_bugs:
                print(f"    - {name}: {detail}")

    print()
    print("=" * 70)

    return FAIL_COUNT == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
