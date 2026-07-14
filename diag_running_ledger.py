"""用【运行代码】(praxis-mcp/src) 诊断账本解析与 reconcile/performance 真实行为。"""
import os, sys
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, SRC)
WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", "")

from praxis.core.ledger import FileLedger
from praxis.core.paths import get_ledger_path

lp = get_ledger_path(WORKSPACE)
print("ledger path =", lp)
print("exists =", os.path.exists(lp))

led = FileLedger(lp)
txs = led.list(limit=1000)
print("ledger.count() =", led.count())
print("ledger.list() len =", len(txs))
if txs:
    t = txs[0]
    print("sample tx attrs:", [a for a in dir(t) if not a.startswith('_')][:20])
    print("sample .type? ", getattr(t, 'type', 'NA'), " .tx_type? ", getattr(t, 'tx_type', 'NA'))
    print("sample ticker/qty/price:", getattr(t,'ticker','NA'), getattr(t,'quantity','NA'), getattr(t,'price','NA'))

# 逐行手动解析，统计成功/失败
from praxis.core.models import Transaction
ok = bad = 0
errs = []
import json
with open(lp, encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        line=line.strip()
        if not line: continue
        try:
            Transaction(**json.loads(line)); ok += 1
        except Exception as e:
            bad += 1
            if len(errs) < 3: errs.append(f"line{i}: {e}")
print(f"\n手动解析: ok={ok} bad={bad}")
for e in errs: print("  ", e)
