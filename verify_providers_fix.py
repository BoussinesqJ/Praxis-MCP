"""验证 providers 迁移：模拟 MCP 服务器启动后的 registry 注册 + 实际取价。

检查项:
1. registry auto_discover 能正确注册 tencent + mootdx 两个 provider
2. 降级链顺序合理: tencent(5) → mootdx(8)
3. import 无残留错误
4. DataProvider 接口 4 个方法齐全
5. 实际取价测试（tencent HTTP + mootdx TCP）
6. 不破坏现有运行版代码（paths.py / state_builder.py 等昨晚修复）
"""
import sys
import os
import asyncio
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
os.environ.setdefault("PRAXIS_WORKSPACE", os.environ.get("PRAXIS_WORKSPACE", ""))

WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", "")

FAILURES: list[str] = []
PASSES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    """记录检查结果"""
    if condition:
        PASSES.append(name)
        print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILURES.append(name)
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


def test_imports() -> None:
    """测试 1: import 无残留错误"""
    print("\n=== 测试 1: Import 检查 ===")

    # exceptions 模块
    try:
        from praxis.core.exceptions import (
            DataError,
            PraxisError,
            ConfigError,
            ProviderError,
        )
        check("exceptions_import", True)
    except Exception as e:
        check("exceptions_import", False, str(e))
        return

    # DataError 继承链
    check("dataerror_inherits_praxiserror", issubclass(DataError, PraxisError))
    check("dataerror_inherits_exception", issubclass(DataError, Exception))

    # DataError source 属性
    e = DataError("test", source="tencent")
    check("dataerror_source_attr", e.source == "tencent")
    check("dataerror_str", "[tencent]" in str(e))

    # TencentDataProvider
    try:
        from praxis.engine.data.realtime import TencentDataProvider
        check("tencent_import", True)
    except Exception as e:
        check("tencent_import", False, str(e))
        return

    # MootdxProvider
    try:
        from praxis.engine.data.mootdx_provider import MootdxProvider
        check("mootdx_import", True)
    except Exception as e:
        check("mootdx_import", False, str(e))
        return

    # CachedDataProvider（确认未破坏）
    try:
        from praxis.engine.data.provider import CachedDataProvider
        check("cached_provider_import", True)
    except Exception as e:
        check("cached_provider_import", False, str(e))


def test_interface_compliance() -> None:
    """测试 2: DataProvider 接口 4 个方法齐全"""
    print("\n=== 测试 2: 接口合规性 ===")

    from praxis.core.interfaces import DataProvider
    from praxis.engine.data.realtime import TencentDataProvider
    from praxis.engine.data.mootdx_provider import MootdxProvider

    required_methods = ["get_realtime_quote", "get_history_kline", "get_fund_nav", "close"]

    for cls_name, cls in [("TencentDataProvider", TencentDataProvider),
                           ("MootdxProvider", MootdxProvider)]:
        # 继承 DataProvider
        check(f"{cls_name}_inherits_dataprovider", issubclass(cls, DataProvider))

        # 4 个方法齐全
        for method in required_methods:
            has_method = hasattr(cls, method)
            check(f"{cls_name}_{method}", has_method)

        # 方法是协程
        for method in required_methods:
            if hasattr(cls, method):
                func = getattr(cls, method)
                is_async = inspect.iscoroutinefunction(func)
                check(f"{cls_name}_{method}_async", is_async)


def test_registry() -> None:
    """测试 3: registry auto_discover 注册"""
    print("\n=== 测试 3: Registry 注册 ===")

    from praxis.engine.data.registry import ProviderRegistry

    reg = ProviderRegistry()
    reg._discover_builtin()

    providers = reg.list_providers()
    provider_names = [p["name"] for p in providers]

    check("registry_has_tencent", "tencent" in provider_names)
    check("registry_has_mootdx", "mootdx" in provider_names)
    check("registry_provider_count", len(providers) == 2, f"got {len(providers)}")

    # 优先级检查
    for p in providers:
        if p["name"] == "tencent":
            check("tencent_priority", p["priority"] == 5, f"got {p['priority']}")
        if p["name"] == "mootdx":
            check("mootdx_priority", p["priority"] == 8, f"got {p['priority']}")

    # 降级链顺序
    chain = reg.get_chain()
    chain_names = [name for name, _ in chain]
    check("chain_not_empty", len(chain) > 0)
    check("chain_order", chain_names == ["tencent", "mootdx"], f"got {chain_names}")
    check("chain_tencent_first", chain_names[0] == "tencent" if chain_names else False)


async def test_real_fetch() -> None:
    """测试 4: 实际取价测试"""
    print("\n=== 测试 4: 实际取价测试 ===")

    test_tickers = ["600519", "000001"]  # 贵州茅台, 平安银行

    # 测试 TencentDataProvider
    print("\n  --- TencentDataProvider (HTTP) ---")
    try:
        from praxis.engine.data.realtime import TencentDataProvider

        tp = TencentDataProvider()
        quotes = await tp.get_realtime_quote(test_tickers)
        check("tencent_realtime_not_empty", len(quotes) > 0, f"got {len(quotes)} tickers")

        if quotes:
            for ticker, data in quotes.items():
                price = data.get("price", 0)
                check(f"tencent_{ticker}_price", price > 0, f"price={price}")
                check(f"tencent_{ticker}_source", data.get("source") == "tencent")

        await tp.close()
    except Exception as e:
        check("tencent_realtime", False, f"Exception: {e}")

    # 测试 MootdxProvider
    print("\n  --- MootdxProvider (TCP) ---")
    try:
        from praxis.engine.data.mootdx_provider import MootdxProvider

        mp = MootdxProvider()
        if mp._client is None:
            check("mootdx_client_init", False, "client is None")
        else:
            check("mootdx_client_init", True)

            quotes = await mp.get_realtime_quote(test_tickers)
            check("mootdx_realtime_not_empty", len(quotes) > 0, f"got {len(quotes)} tickers")

            if quotes:
                for ticker, data in quotes.items():
                    price = data.get("price", 0)
                    check(f"mootdx_{ticker}_price", price > 0, f"price={price}")
                    check(f"mootdx_{ticker}_source", data.get("source") == "mootdx")

            # 测试 K 线
            klines = await mp.get_history_kline("600519", period="day", count=5)
            check("mootdx_kline_not_empty", len(klines) > 0, f"got {len(klines)} bars")
            if klines:
                first = klines[0]
                check("mootdx_kline_has_date", "date" in first)
                check("mootdx_kline_has_close", "close" in first)

        await mp.close()
    except Exception as e:
        check("mootdx_realtime", False, f"Exception: {e}")

    # 测试 CachedDataProvider（完整降级链）
    print("\n  --- CachedDataProvider (降级链) ---")
    try:
        from praxis.engine.data.provider import CachedDataProvider

        cp = CachedDataProvider(workspace=WORKSPACE)
        providers = cp.list_providers()
        provider_names = [p["name"] for p in providers]
        # 内置 provider 必须存在（workspace 插件可能额外注册）
        check("cached_has_tencent", "tencent" in provider_names)
        check("cached_has_mootdx", "mootdx" in provider_names)
        check("cached_provider_count_ge2", len(providers) >= 2, f"got {len(providers)}")

        quotes = await cp.get_realtime_quote(test_tickers)
        check("cached_realtime_not_empty", len(quotes) > 0, f"got {len(quotes)} tickers")

        prices = await cp.get_prices(test_tickers)
        check("cached_prices_not_empty", len(prices) > 0)
        for ticker, price in prices.items():
            check(f"cached_{ticker}_price", price > 0, f"price={price}")

        await cp.close()
    except Exception as e:
        check("cached_provider", False, f"Exception: {e}")


def test_no_breakage() -> None:
    """测试 5: 不破坏现有运行版代码"""
    print("\n=== 测试 5: 现有代码未破坏 ===")

    # paths.py
    try:
        from praxis.core.paths import get_paths, get_ledger_path
        paths = get_paths(WORKSPACE)
        check("paths_module", True)
    except Exception as e:
        check("paths_module", False, str(e))

    # state_builder
    try:
        from praxis.engine.state_builder import LedgerStateBuilder
        check("state_builder_import", True)
    except Exception as e:
        check("state_builder_import", False, str(e))

    # ledger
    try:
        from praxis.core.ledger import FileLedger
        check("ledger_import", True)
    except Exception as e:
        check("ledger_import", False, str(e))

    # models
    try:
        from praxis.core.models import Portfolio, Transaction
        check("models_import", True)
    except Exception as e:
        check("models_import", False, str(e))

    # interfaces
    try:
        from praxis.core.interfaces import DataProvider
        check("interfaces_import", True)
    except Exception as e:
        check("interfaces_import", False, str(e))

    # 备份文件存在
    import pathlib
    bak = pathlib.Path(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "praxis", "engine", "data", "registry.py.bak-providers")
    )
    check("registry_backup_exists", bak.exists())

    # httpx 版本正确（MCP 兼容）
    import httpx
    check("httpx_version_compatible", httpx.__version__ >= "0.27.1", f"v{httpx.__version__}")

    # mootdx 已安装
    try:
        import mootdx
        check("mootdx_installed", True, f"v{mootdx.__version__}")
    except ImportError:
        check("mootdx_installed", False, "not installed")


def main() -> None:
    print("=" * 60)
    print("PRAXIS Providers 迁移验证")
    print("=" * 60)

    test_imports()
    test_interface_compliance()
    test_registry()
    test_no_breakage()
    asyncio.run(test_real_fetch())

    print("\n" + "=" * 60)
    print(f"总结: {len(PASSES)} PASS, {len(FAILURES)} FAIL")
    print("=" * 60)

    if FAILURES:
        print("\n失败项:")
        for f in FAILURES:
            print(f"  [FAIL] {f}")
        print("\nIS_PASS: NO")
    else:
        print("\nIS_PASS: YES")


if __name__ == "__main__":
    main()
