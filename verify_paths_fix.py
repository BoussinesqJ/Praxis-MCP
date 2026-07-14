"""验证 0710 路径修复：模拟 MCP 服务器重启后的路径解析与账本加载。"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
os.environ.setdefault("PRAXIS_WORKSPACE", os.environ.get("PRAXIS_WORKSPACE", ""))

WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", "")

from praxis.core.paths import get_paths, get_ledger_path
from praxis.core.ledger import FileLedger

paths = get_paths(WORKSPACE)
print("=== get_paths() 解析结果 ===")
for k, v in paths.items():
    exists = v.exists()
    print(f"  {k:10s} -> {v}   [{'OK' if exists else 'MISSING'}]")

lp = get_ledger_path(WORKSPACE)
print(f"\nget_ledger_path -> {lp}  [{'OK' if lp.exists() else 'MISSING'}]")

nav_f = paths['nav'] / 'default.jsonl'
dec_f = paths['decisions'] / 'decision_records.jsonl'
print(f"nav file        -> {nav_f}  [{'OK' if nav_f.exists() else 'MISSING'}]")
print(f"decisions file  -> {dec_f}  [{'OK' if dec_f.exists() else 'MISSING'}]")

print("\n=== FileLedger 加载 ===")
ledger = FileLedger(lp)
txs = ledger.list(limit=1000)
print(f"ledger.count() = {ledger.count()}")
print(f"ledger.list() len = {len(txs)}")

# 净持仓核算
from collections import defaultdict
net = defaultdict(float)
for t in txs:
    q = float(getattr(t, 'quantity', 0) or 0)
    tt = getattr(t, 'tx_type', None)
    ttv = getattr(tt, 'value', tt)
    if ttv in ('buy', 'subscribe'):
        net[t.ticker] += q
    elif ttv in ('sell', 'redeem'):
        net[t.ticker] -= q
print("\n=== 净持仓（去重后按 tx_id 唯一）===")
for tk, v in sorted(net.items()):
    if abs(v) > 1e-6:
        print(f"  {tk}: {v:.0f}")
