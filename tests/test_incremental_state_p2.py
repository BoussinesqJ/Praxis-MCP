"""增量状态重建器测试"""
import pytest
import asyncio
from pathlib import Path
import tempfile

from praxis.core.ledger import FileLedger
from praxis.core.state_builder import SimpleStateBuilder
from praxis.core.database import Database
from praxis.core.models.transaction import Transaction, TransactionType
from praxis.core.models.investor import InvestorProfile, InvestorConstraints, ExecutionConfig, Philosophy
from praxis.core.models.portfolio import Portfolio, AssetEntry
from praxis.core.models.state import PortfolioState


class MockDataProvider:
    async def get_realtime_quote(self, tickers):
        return {t: {"price": 10.0} for t in tickers}
    async def get_history_kline(self, ticker, period="day", count=60):
        return []
    async def get_fund_nav(self, ticker):
        return {}


class MockConfigLoader:
    def load_investor(self, investor_id):
        return InvestorProfile(
            id=investor_id,
            name="Test",
            capital_cny=100000.0,
            risk_level="medium",
            style="grid_value",
            philosophy=Philosophy(beliefs=["grid"], defenses=[]),
            constraints=InvestorConstraints(
                banned_markets=[],
                banned_instruments=[],
                etf_exemption=True,
            ),
            execution=ExecutionConfig(
                min_transaction_cny=100.0
            )
        )

    def load_portfolio(self, investor_id, portfolio_id):
        return Portfolio(
            strategy_type="grid_value",
            strategy_template="grid_value",
            created_at="2026-01-01",
            version="1.0",
            assets=[
                AssetEntry(
                    ticker="600995",
                    name="电力股",
                    type="stock",
                    category="power_infra",
                    target_weight_pct=20.0
                )
            ]
        )


def test_incremental_state_rebuild():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        ledger_path = Path(tmpdir) / "transactions.jsonl"
        
        # 1. 实例化 ledger 和 增量 state builder
        ledger = FileLedger(ledger_path, db=db)
        provider = MockDataProvider()
        loader = MockConfigLoader()
        builder = SimpleStateBuilder(ledger, loader, provider, db=db)
        
        async def run_test():
            # 2. 空 ledger 时重建
            state1 = await builder.rebuild("example", "demo")
            assert state1.cash.total_assets == 100000.0
            
            # 3. 增加一条交易记录
            tx = Transaction(
                tx_id="",
                type=TransactionType.BUY,
                ticker="600995",
                quantity=100.0,
                price=10.0,
                fee=5.0,
                investor_id="example",
                portfolio_id="demo"
            )
            ledger.append(tx)
            
            # 4. 再次重建（此时会使用增量计算逻辑）
            state2 = await builder.rebuild("example", "demo")
            # 初始资金 (100000) - 买入花费 (1000 + 5) = 可用现金 (98995)
            # 持仓市值 (100 * 10 = 1000)
            # 总资产 = 98995 + 1000 = 99995
            assert state2.cash.available_cash == 98995.0
            assert state2.cash.total_assets == 99995.0
            
            # 5. 验证 state_caches 表中是否有对应的缓存数据
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM state_caches WHERE investor_id='example'")
                row = cursor.fetchone()
                assert row is not None
                assert row["last_processed_tx_id"] is not None
                
            # 6. 不使用缓存时的全量重建进行对比
            builder_full = SimpleStateBuilder(ledger, loader, provider, db=None)
            state_full = await builder_full.rebuild("example", "demo")
            
            assert state2.cash.available_cash == state_full.cash.available_cash
            assert state2.cash.total_assets == state_full.cash.total_assets
            assert state2.positions[0].quantity == state_full.positions[0].quantity

        asyncio.run(run_test())
