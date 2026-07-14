"""终验：模拟重启后服务端，完整跑通 reconcile + nav 读取

不依赖运行中 MCP 进程，直接用修复后的代码构造引擎并验证：
1. reconcile(dry_run=False) 经 StateBuilder 从账本推导真实状态
2. nav_tracker 读取重建后的 default.jsonl（无种子垃圾）
"""
from __future__ import annotations
import asyncio, sys, json
sys.path.insert(0, "src")

from praxis.core.paths import get_paths, get_ledger_path
from praxis.core.ledger import FileLedger
from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.reconciliation import ReconciliationEngine
from praxis.engine.state_builder import LedgerStateBuilder
from praxis.engine.nav_tracker import NavTracker

import os
WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", "")
INV, PORT = "YOUR_INVESTOR", "YOUR_PORTFOLIO"
REAL_PRICES = {"TICKER_A": 0.0, "TICKER_B": 0.0}  # 运行前替换为实际标的和收盘价


class FakeProvider:
    async def get_realtime_quote(self, tickers):
        return {t: {"price": REAL_PRICES[t]} for t in tickers if t in REAL_PRICES}


async def run():
    paths = get_paths(WORKSPACE)
    cl = YamlConfigLoader(WORKSPACE)
    ledger = FileLedger(get_ledger_path(WORKSPACE))
    provider = FakeProvider()
    sb = LedgerStateBuilder(provider, ledger, cl)
    engine = ReconciliationEngine(cl, provider, ledger=ledger, state_builder=sb)

    print("═══ [1] reconcile 对账（重启后服务端等效） ═══")
    res = await engine.reconcile(INV, PORT, None, dry_run=False)
    assert res["success"], res
    d = res["data"]
    print(f"  总资产   = {d['total_assets']}")
    print(f"  持仓市值 = {d['total_market_value']}")
    print(f"  现金     = {d['cash']['total_cash']}")
    for p in d["positions"]:
        print(f"   {p['ticker']:>7} ×{p['quantity']:<6} 均价{p['avg_cost']:<8} 现价{p['current_price']:<8} 市值{p['market_value']:<8} 浮盈{p['unrealized_pnl']}")
    assert d["total_assets"] > 0, f"总资产异常: {d['total_assets']}"
    assert d["cash"]["total_cash"] >= 0
    for p in d["positions"]:
        assert p["ticker"], "持仓标的不应为空"
    print("  ✅ reconcile 修复生效：返回真实账本状态")

    print("\n═══ [2] nav_tracker 读取重建后历史 ═══")
    nav_path = paths["nav"] / "default.jsonl"
    tracker = NavTracker(nav_path, ledger, provider)
    hist = tracker.get_history(60)
    garbage = [h for h in hist if float(h.get("nav", 0)) >= 100]
    print(f"  记录数 = {len(hist)}，种子垃圾行 = {len(garbage)}")
    assert len(garbage) == 0, "仍存在种子垃圾行！"
    last = hist[-1]
    print(f"  末行 {last['date']}: nav={last['nav']} total_assets={last['total_assets']}")
    assert last["date"] and last["nav"] > 0
    print("  ✅ NAV 历史已重建：无垃圾，数据有效")

    print("\nFINAL E2E CHECK DONE ✅")


asyncio.run(run())
