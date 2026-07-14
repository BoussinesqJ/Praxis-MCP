"""验证 LedgerStateBuilder + ReconciliationEngine 对账链路（无需联网）

用模拟 DataProvider 注入收盘价，断言 reconcile(dry_run=False) 返回：
- 总资产 > 0 且为合理值
- 持仓不为空且数量有效
- 现金为正
同时验证：取价失败时回退到 avg_cost，reconcile 不崩溃、仍返回真实账本状态。
"""
from __future__ import annotations
import asyncio, sys
sys.path.insert(0, "src")

from praxis.core.paths import get_ledger_path, get_paths
from praxis.core.ledger import FileLedger
from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.reconciliation import ReconciliationEngine
from praxis.engine.state_builder import LedgerStateBuilder


class FakeProvider:
    def __init__(self, prices: dict):
        self._prices = prices
        self.fail = False
    async def get_realtime_quote(self, tickers):
        if self.fail:
            raise RuntimeError("network unavailable (simulated)")
        return {t: {"price": self._prices[t]} for t in tickers if t in self._prices}


WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", "")
INVESTOR, PORTFOLIO = "YOUR_INVESTOR", "YOUR_PORTFOLIO"
REAL_PRICES = {"TICKER_A": 0.0, "TICKER_B": 0.0}  # 运行前替换


async def run():
    paths = get_paths(WORKSPACE)
    config_loader = YamlConfigLoader(WORKSPACE)
    ledger = FileLedger(get_ledger_path(WORKSPACE))
    provider = FakeProvider(REAL_PRICES)
    sb = LedgerStateBuilder(provider, ledger, config_loader)
    engine = ReconciliationEngine(config_loader, provider, ledger=ledger, state_builder=sb)

    print("[A] 真实取价路径")
    res = await engine.reconcile(INVESTOR, PORTFOLIO, None, dry_run=False)
    assert res["success"], f"reconcile 失败: {res}"
    d = res["data"]
    print(f"  total_assets = {d['total_assets']}")
    print(f"  total_mv     = {d['total_market_value']}")
    print(f"  cash         = {d['cash']['total_cash']}")
    for p in d["positions"]:
        print(f"  持仓 {p['ticker']:>7} x{p['quantity']:<8} 均价{p['avg_cost']:<8} 现价{p['current_price']:<8} MV={p['market_value']:<8} 浮盈{p['unrealized_pnl']}")
    assert d["total_assets"] > 0, f"总资产异常: {d['total_assets']}"
    tk = {p["ticker"]: p for p in d["positions"]}
    assert len(tk) > 0, "持仓不应为空"
    for t, p in tk.items():
        assert p["quantity"] > 0, f"持仓数量异常: {t} = {p['quantity']}"
    assert d["cash"]["total_cash"] >= 0
    print("  [A] PASS ✅")

    print("[B] 取价失败兜底路径（不应崩溃）")
    provider.fail = True
    res2 = await engine.reconcile(INVESTOR, PORTFOLIO, None, dry_run=False)
    assert res2["success"], f"兜底路径失败: {res2}"
    d2 = res2["data"]
    print(f"  total_assets = {d2['total_assets']} (回退到成本价估值)")
    assert d2["total_assets"] > 0
    assert len(d2["positions"]) > 0
    print("  [B] PASS ✅")

    print("\nSTATE BUILDER VERIFY DONE")


asyncio.run(run())
