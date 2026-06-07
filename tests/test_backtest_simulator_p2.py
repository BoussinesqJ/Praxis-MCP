"""基于规则的回测模拟器测试"""
import pytest
import asyncio
from praxis.engine.backtest_simulator import RuleBasedBacktestEngine
from praxis.core.models.investor import InvestorProfile, InvestorConstraints, ExecutionConfig, Philosophy
from praxis.core.models.portfolio import Portfolio, AssetEntry, GridLevel
from praxis.engine.backtest import BacktestResult


class MockDataProvider:
    async def get_history_kline(self, ticker, period="day", count=500):
        if ticker == "000300":
            return [
                {"date": "2026-06-01", "close": 3000.0},
                {"date": "2026-06-02", "close": 3100.0},
                {"date": "2026-06-03", "close": 2900.0},
            ]
        # 模拟 3 天 K 线：下跌后反弹
        return [
            {"date": "2026-06-01", "open": 4.0, "high": 4.1, "low": 3.9, "close": 4.0},
            {"date": "2026-06-02", "open": 4.0, "high": 4.0, "low": 3.7, "close": 3.8}, # 触发 trigger_pct: -3.0 (即价格 3.88)
            {"date": "2026-06-03", "open": 3.8, "high": 3.9, "low": 3.75, "close": 3.85},
        ]

    async def get_realtime_quote(self, tickers):
        return {}


class MockConfigLoader:
    def load_investor(self, investor_id):
        return InvestorProfile(
            id=investor_id,
            name="Test",
            capital_cny=70000.0,
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
                    ticker="ETF_300",
                    name="沪深300ETF",
                    type="etf",
                    category="defensive_base",
                    target_weight_pct=50.0,
                    base_price=4.0,
                    grid=[
                        GridLevel(trigger_pct=-3.0, shares=1000, label="第一档", status="active")
                    ]
                )
            ]
        )


def test_rule_based_backtest_simulator():
    provider = MockDataProvider()
    loader = MockConfigLoader()
    engine = RuleBasedBacktestEngine(provider, loader, initial_capital=70000.0)
    
    async def run_test():
        result = await engine.run_backtest(
            investor_id="example",
            portfolio_id="demo",
            start_date="2026-06-01",
            end_date="2026-06-03",
            benchmark="000300"
        )
        
        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 70000.0
        # 触发了网格买入，买入 1000 股 @ 3.88，手续费为 max(5.0, 1000 * 3.88 * 0.0003) = 5.0
        # 买入支出: 3880 + 5 = 3885
        # 最终市值 (1000 * 3.85 = 3850)
        # 最终现金 (70000 - 3885 = 66115)
        # 最终资产值 = 66115 + 3850 = 69965
        assert result.final_value == 69965.0
        assert result.total_trades == 0  # 仅有买入，没有完成闭环交易
        assert result.total_fee == 5.0   # 买入交易产生的手续费
        assert result.total_return < 0
        assert result.max_drawdown >= 0
        assert result.win_rate == 0.0

    asyncio.run(run_test())
