"""P0 - 绩效计算器正确性测试"""
import os
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile

from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType, TransactionStatus
from praxis.engine.performance import EnhancedPerformanceCalculator
from praxis.tools.performance import get_performance


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 1. 创建投资者与组合配置
        investors_dir = tmp_path / "investors"
        inv_dir = investors_dir / "example"
        inv_dir.mkdir(parents=True)
        with open(inv_dir / "profile.yaml", "w", encoding="utf-8") as f:
            f.write("""
investor:
  name: "Example Investor"
  id: "example"
  capital_cny: 100000
  risk_level: "C3"
  style: "balanced"
""")
        # 组合
        port_dir = inv_dir / "portfolios" / "demo"
        port_dir.mkdir(parents=True)
        with open(port_dir / "portfolio.yaml", "w", encoding="utf-8") as f:
            f.write("""
portfolio:
  strategy_type: "grid_value"
  strategy_template: "grid_value"
  created_at: "2026-05-18"
  version: "v9.0"
assets:
  - ticker: "600995"
    name: "南网储能"
    type: "stock"
    category: "power_infra"
    target_weight_pct: 20
""")
            
        yield tmp_path


def test_performance_capital_override(temp_workspace):
    """测试 get_performance 能够读取实际的 100,000 元初始资金计算收益率"""
    ledger_path = temp_workspace / "data" / "ledger" / "transactions.jsonl"
    ledger = FileLedger(ledger_path)
    
    # 写入一笔分红 7,000 元
    tx = Transaction(
        tx_id="tx-20260607-001",
        type=TransactionType.DIVIDEND,
        ticker="600995",
        quantity=0,
        price=7000.0, # price 复用为分红金额
        fee=0.0,
        status=TransactionStatus.CONFIRMED,
        investor_id="example",
        portfolio_id="demo"
    )
    ledger.append(tx)
    
    # 计算绩效
    import asyncio
    result = asyncio.run(
        get_performance(
            investor="example",
            portfolio="demo",
            workspace=str(temp_workspace)
        )
    )
    
    assert result["success"] is True
    metrics = result["data"]["metrics"]
    # 初始资金应为 100,000，所以 7000 元分红的收益率应为 7% (0.07)，而不是 7000 / 70000 = 10% (0.10)
    assert abs(metrics["total_return"] - 0.07) < 0.001


def test_performance_win_rate_and_profit_loss(temp_workspace):
    """测试排除后视偏差后的胜率计算和盈亏比计算"""
    ledger_path = temp_workspace / "data" / "ledger" / "transactions.jsonl"
    ledger = FileLedger(ledger_path)
    
    # 场景：
    # Day 1: Buy 100 shares @ $10.0 (Cost = 1000)
    # Day 2: Sell 100 shares @ $12.0 (Win, PnL = +200)
    # Day 3: Buy 100 shares @ $15.0 (Cost = 1500)
    # (如果存在后视偏差，Day 2 的 sell 会对比 [10, 15] 的均价 12.5，判定为 Loss！
    # 如果无后视偏差，Day 2 的 sell 只对比在它之前发生的 Day 1 买入 $10.0，判定为 Win！)
    
    base_time = datetime.now(timezone.utc)
    
    tx_buy1 = Transaction(
        tx_id="tx-buy-1",
        type=TransactionType.BUY,
        ticker="600995",
        quantity=100,
        price=10.0,
        fee=0.0,
        created_at=base_time - timedelta(days=2),
        status=TransactionStatus.CONFIRMED,
        investor_id="example",
        portfolio_id="demo"
    )
    ledger.append(tx_buy1)
    
    tx_sell1 = Transaction(
        tx_id="tx-sell-1",
        type=TransactionType.SELL,
        ticker="600995",
        quantity=100,
        price=12.0,
        fee=0.0,
        created_at=base_time - timedelta(days=1),
        status=TransactionStatus.CONFIRMED,
        investor_id="example",
        portfolio_id="demo"
    )
    ledger.append(tx_sell1)
    
    tx_buy2 = Transaction(
        tx_id="tx-buy-2",
        type=TransactionType.BUY,
        ticker="600995",
        quantity=100,
        price=15.0,
        fee=0.0,
        created_at=base_time,
        status=TransactionStatus.CONFIRMED,
        investor_id="example",
        portfolio_id="demo"
    )
    ledger.append(tx_buy2)
    
    calculator = EnhancedPerformanceCalculator(ledger, initial_capital=100000)
    metrics = calculator.calculate("example", "demo")
    
    # 胜率应该为 100% (1.0)，因为唯一的卖出是赢的
    assert metrics.win_rate == 1.0
    # 赢家盈利应为 200，亏损为 0，盈亏比应为 0 (或处理为 0)
    assert metrics.profit_loss_ratio == 0.0
    
    # 再增加一笔亏损交易：
    # Day 4: Sell 50 shares @ $8.0 (Loss, PnL = 50 * (8 - 12.5) = -225)
    # (此时均价为 (1000+1500)/200 = 12.5)
    tx_sell2 = Transaction(
        tx_id="tx-sell-2",
        type=TransactionType.SELL,
        ticker="600995",
        quantity=50,
        price=8.0,
        fee=0.0,
        created_at=base_time + timedelta(days=1),
        status=TransactionStatus.CONFIRMED,
        investor_id="example",
        portfolio_id="demo"
    )
    ledger.append(tx_sell2)
    
    metrics2 = calculator.calculate("example", "demo")
    # 2 笔交易，1 赢 1 输，胜率 50%
    assert metrics2.win_rate == 0.5
    # 赢：trade1 pnl = 100 * (12 - 10) = 200
    # 输：trade2 pnl = 50 * (8 - 12.5) = -225 (绝对值 225)
    # 盈亏比 = 200 / 225 = 0.8888...
    assert abs(metrics2.profit_loss_ratio - (200 / 225)) < 0.001
