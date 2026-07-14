"""验证 performance 修复：total_return 应从 NAV 序列计算（不再为 0）"""
import sys
import os
import json
from pathlib import Path

# 设置路径
workspace = os.environ.get("PRAXIS_WORKSPACE", "")
sys.path.insert(0, str(Path(__file__).parent / "src"))

from praxis.engine.performance import EnhancedPerformanceCalculator
from praxis.core.ledger import FileLedger

# 模拟 NavTracker（直接读取 default.jsonl）
class MockNavTracker:
    def __init__(self, nav_path):
        self._path = Path(nav_path)
        self._records = []
        if self._path.exists():
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self._records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    def get_history(self, days=365):
        history = self._records[-days:]
        return {"success": True, "data": {"records": history, "count": len(history)}}


# 加载
ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
nav_path = Path(workspace) / "data" / "nav" / "default.jsonl"

print(f"ledger: {ledger_path} (exists={ledger_path.exists()})")
print(f"nav:    {nav_path} (exists={nav_path.exists()})")

ledger = FileLedger(ledger_path)
nav_tracker = MockNavTracker(nav_path)

print(f"nav_records: {len(nav_tracker._records)}")

calc = EnhancedPerformanceCalculator(ledger, nav_tracker=nav_tracker)
result = calc.calculate("YOUR_INVESTOR", "YOUR_PORTFOLIO")

print("\n=== Performance 修复验证 ===")
if result.get("success"):
    data = result["data"]
    print(f"total_return:      {data['total_return']}  (期望: -0.0005 = -0.05%)")
    print(f"annualized_return: {data['annualized_return']}")
    print(f"max_drawdown:      {data['max_drawdown']}  (期望: ~0.027 = 2.7%)")
    print(f"volatility:        {data['volatility']}  (年化)")
    print(f"sharpe_ratio:      {data['sharpe_ratio']}")
    print(f"calmar_ratio:      {data['calmar_ratio']}")
    print(f"benchmark_return:  {data['benchmark_return']}")
    print(f"excess_return:     {data['excess_return']}")
    print(f"win_rate:          {data['win_rate']}")
    print(f"profit_loss_ratio: {data['profit_loss_ratio']}")
    print(f"turnover_rate:     {data['turnover_rate']}")
    print(f"total_fee:         {data['total_fee']}")

    if data["total_return"] != 0:
        print("\n[PASS] 修复成功: total_return 不再为 0")
        sys.exit(0)
    else:
        print("\n[FAIL] 修复失败: total_return 仍为 0")
        sys.exit(1)
else:
    print(f"[FAIL] 计算失败: {result.get('error')}")
    sys.exit(1)
