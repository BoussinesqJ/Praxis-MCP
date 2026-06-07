"""P0 - 风控约束动态状态测试"""
import os
import pytest
import asyncio
from pathlib import Path
import tempfile

from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType, TransactionStatus
from praxis.tools.engine import check_constraints


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
constraints:
  banned_markets: []
  banned_instruments: []
  etf_exemption: true
execution:
  min_transaction_cny: 1000
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


def test_constraints_with_real_ledger_cash(temp_workspace):
    """测试 check_constraints 是否基于账本真实可用现金，正确触发现金底线阻止"""
    from unittest.mock import patch, AsyncMock
    ledger_path = temp_workspace / "data" / "ledger" / "transactions.jsonl"
    ledger = FileLedger(ledger_path)
    
    # 现金底线是 40% (即 40000)。
    # 1. 写入一笔大额交易，花掉 55,000 元（剩 45,000）
    tx = Transaction(
        tx_id="tx-20260607-001",
        type=TransactionType.BUY,
        ticker="600995",
        quantity=5500,
        price=10.0,
        fee=0.0,
        status=TransactionStatus.CONFIRMED,
        investor_id="example",
        portfolio_id="demo"
    )
    ledger.append(tx)
    
    # 2. 尝试再次买入 10,000 元，因为交易后现金将降至 35,000 (< 40,000 底线)，应当被 hard_block！
    with patch("praxis.engine.data.provider.CachedDataProvider.get_realtime_quote", new_callable=AsyncMock) as mock_quote:
        mock_quote.return_value = {"600995": {"price": 10.0}}
        result = check_constraints(
            investor="example",
            portfolio="demo",
            action="buy",
            ticker="600995",
            amount=10000,
            workspace=str(temp_workspace)
        )
    
    assert result["success"] is True
    data = result["data"]
    
    # 应该没有通过
    assert data["all_passed"] is False
    # 应该有阻止原因，并且是现金底线
    assert len(data["blocked"]) > 0
    blocked_rules = [b["rule"] for b in data["blocked"]]
    assert "risk_rules.cash_floor" in blocked_rules
    assert "35.0%" in data["blocked"][0]["message"]
