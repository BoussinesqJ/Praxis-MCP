"""P0 - 多投资者/多组合隔离测试"""
import os
import pytest
import asyncio
from pathlib import Path
import tempfile

from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType, TransactionStatus
from praxis.core.state_builder import SimpleStateBuilder
from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.data.provider import CachedDataProvider


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # 1. 创建 2 个不同的投资者配置
        investors_dir = tmp_path / "investors"
        
        # 投资者 A
        inv_a_dir = investors_dir / "investor_a"
        inv_a_dir.mkdir(parents=True)
        with open(inv_a_dir / "profile.yaml", "w", encoding="utf-8") as f:
            f.write("""
investor:
  name: "Investor A"
  id: "investor_a"
  capital_cny: 100000
  risk_level: "C3"
  style: "balanced"
""")
        # 组合 A
        port_a_dir = inv_a_dir / "portfolios" / "portfolio_a"
        port_a_dir.mkdir(parents=True)
        with open(port_a_dir / "portfolio.yaml", "w", encoding="utf-8") as f:
            f.write("""
portfolio:
  strategy_type: "grid_value"
  strategy_template: "grid_value"
  created_at: "2026-05-18"
  version: "v1.0"
assets:
  - ticker: "STOCK_A"
    name: "示例股票A"
    type: "stock"
    category: "power_infra"
    target_weight_pct: 20
""")

        # 投资者 B
        inv_b_dir = investors_dir / "investor_b"
        inv_b_dir.mkdir(parents=True)
        with open(inv_b_dir / "profile.yaml", "w", encoding="utf-8") as f:
            f.write("""
investor:
  name: "Investor B"
  id: "investor_b"
  capital_cny: 200000
  risk_level: "C3"
  style: "balanced"
""")
        # 组合 B
        port_b_dir = inv_b_dir / "portfolios" / "portfolio_b"
        port_b_dir.mkdir(parents=True)
        with open(port_b_dir / "portfolio.yaml", "w", encoding="utf-8") as f:
            f.write("""
portfolio:
  strategy_type: "grid_value"
  strategy_template: "grid_value"
  created_at: "2026-05-18"
  version: "v1.0"
assets:
  - ticker: "STOCK_A"
    name: "示例股票A"
    type: "stock"
    category: "power_infra"
    target_weight_pct: 20
""")
            
        yield tmp_path


def test_portfolio_isolation(temp_workspace):
    """测试不同投资者的交易账本隔离"""
    ledger_path = temp_workspace / "data" / "ledger" / "transactions.jsonl"
    ledger = FileLedger(ledger_path)
    
    # 1. 投资者 A 购买 STOCK_A (1000 股 @ 10 元)
    tx_a = Transaction(
        tx_id="tx-20260607-001",
        type=TransactionType.BUY,
        ticker="STOCK_A",
        quantity=1000,
        price=10.0,
        fee=5.0,
        status=TransactionStatus.CONFIRMED,
        investor_id="investor_a",
        portfolio_id="portfolio_a"
    )
    ledger.append(tx_a)
    
    # 2. 投资者 B 购买 STOCK_A (2000 股 @ 12 元)
    tx_b = Transaction(
        tx_id="tx-20260607-002",
        type=TransactionType.BUY,
        ticker="STOCK_A",
        quantity=2000,
        price=12.0,
        fee=6.0,
        status=TransactionStatus.CONFIRMED,
        investor_id="investor_b",
        portfolio_id="portfolio_b"
    )
    ledger.append(tx_b)
    
    # 加载配置和数据源
    config_loader = YamlConfigLoader(temp_workspace)
    data_provider = CachedDataProvider(workspace=temp_workspace)
    
    # Mock 行情数据以避免真实网络请求
    market_data = {"STOCK_A": {"price": 11.0}}
    
    async def run_test():
        builder = SimpleStateBuilder(ledger, config_loader, data_provider)
        
        # 重建 投资者 A 的状态
        state_a = await builder.rebuild("investor_a", "portfolio_a", market_data=market_data)
        
        # 重建 投资者 B 的状态
        state_b = await builder.rebuild("investor_b", "portfolio_b", market_data=market_data)
        
        # 验证隔离性：
        # Investor A 资金：100000 - (1000 * 10 + 5) = 89995
        assert state_a.cash.available_cash == 89995.0
        # Investor A 持仓：1000 股
        assert len(state_a.positions) == 1
        assert state_a.positions[0].quantity == 1000
        assert state_a.positions[0].avg_cost == 10.005 # (10000 + 5) / 1000
        
        # Investor B 资金：200000 - (2000 * 12 + 6) = 175994
        assert state_b.cash.available_cash == 175994.0
        # Investor B 持仓：2000 股
        assert len(state_b.positions) == 1
        assert state_b.positions[0].quantity == 2000
        assert state_b.positions[0].avg_cost == 12.003 # (24000 + 6) / 2000
        
        await data_provider.close()

    asyncio.run(run_test())
