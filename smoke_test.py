"""0710 修复综合冒烟测试：模拟 MCP 服务器 initialize 后各引擎读取真实数据。"""
import sys, os, asyncio
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", "")
os.environ["PRAXIS_WORKSPACE"] = WORKSPACE

from praxis.core.paths import get_paths, get_ledger_path
from praxis.core.ledger import FileLedger
from praxis.engine.performance import EnhancedPerformanceCalculator
from praxis.engine.nav_tracker import NavTracker

paths = get_paths(WORKSPACE)
ledger = FileLedger(get_ledger_path(WORKSPACE))
print(f"[1] FileLedger.count() = {ledger.count()}  (期望 20)")

# performance
perf = EnhancedPerformanceCalculator(ledger)
txs = ledger.list(limit=1000)
buys = [t for t in txs if getattr(t, 'tx_type', None) and getattr(t.tx_type,'value',t.tx_type)=='buy']
sells = [t for t in txs if getattr(t, 'tx_type', None) and getattr(t.tx_type,'value',t.tx_type)=='sell']
print(f"[2] performance 可读交易: 总 {len(txs)} 条, buy={len(buys)}, sell={len(sells)}  (原为'无交易记录')")

# nav history
nav_file = paths['nav'] / 'default.jsonl'
nt = NavTracker(nav_file, ledger, None)
try:
    hist = nt.get_history(60)
    n = len(hist.get('history', hist)) if isinstance(hist, dict) else len(hist)
    print(f"[3] nav_tracker.get_history(60) 返回条目 ~= {n}  (文件: {nav_file.name})")
except Exception as e:
    print(f"[3] nav history 读取异常: {e}")

# nav_module handler 与 schema 对齐（回归）
import inspect
from praxis.tools import nav_module
from praxis.tools._schemas import NavInput
h = set(inspect.signature(nav_module.nav).parameters) - {'_deps'}
s = set(NavInput.model_fields)
print(f"[4] nav handler/schema 对齐: {'OK' if h==s else 'MISMATCH '+str(s-h)}")

print("\nSMOKE TEST DONE")
