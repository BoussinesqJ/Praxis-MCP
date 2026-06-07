"""MCP 工具 - 回测引擎"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.engine.backtest import SimpleBacktestEngine, BacktestConfig
from praxis.engine.data.benchmark import TencentBenchmarkProvider


async def run_backtest(
    strategy_name: str,
    investor: str,
    portfolio: str,
    days: int = 90,
    workspace: str = ".",
    rule_based: bool = False,
) -> dict:
    """运行策略回测"""
    try:
        # 计算回测期间
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        if rule_based:
            from praxis.engine.data.provider import CachedDataProvider
            from praxis.engine.config_loader import YamlConfigLoader
            from praxis.engine.backtest_simulator import RuleBasedBacktestEngine

            data_provider = CachedDataProvider(workspace=workspace)
            config_loader = YamlConfigLoader(workspace=workspace)

            engine = RuleBasedBacktestEngine(data_provider, config_loader)
            result = await engine.run_backtest(
                investor_id=investor,
                portfolio_id=portfolio,
                start_date=start_date,
                end_date=end_date,
            )

            formatted = f"=== 规则回测模拟结果 ===\n" \
                        f"开始日期: {result.start_date}\n" \
                        f"结束日期: {result.end_date}\n" \
                        f"初始资金: ¥{result.initial_capital:,.2f}\n" \
                        f"最终资产: ¥{result.final_value:,.2f}\n" \
                        f"总收益率: {result.total_return:.2%}\n" \
                        f"年化收益率: {result.annualized_return:.2%}\n" \
                        f"最大回撤: {result.max_drawdown:.2%}\n" \
                        f"夏普比率: {result.sharpe_ratio:.2f}\n" \
                        f"总成交数: {result.total_trades}\n" \
                        f"总手续费: ¥{result.total_fee:,.2f}\n" \
                        f"胜率: {result.win_rate:.1%}\n"
            if result.benchmark_return is not None:
                formatted += f"基准收益率: {result.benchmark_return:.2%}\n"
                formatted += f"超额收益率: {result.excess_return:.2%}\n"

            return {
                "success": True,
                "data": {
                    "result": result.model_dump(),
                    "formatted": formatted,
                },
            }
        else:
            ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
            ledger = FileLedger(ledger_path)
            engine = SimpleBacktestEngine(ledger)

            config = BacktestConfig(
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
            )

            # 获取基准数据
            benchmark_series = None
            try:
                provider = TencentBenchmarkProvider()
                kline = await provider.get_daily_kline("000300", start_date, end_date)
                if kline:
                    benchmark_series = [{"date": k["date"], "close": k["close"]} for k in kline]
                await provider.close()
            except Exception:
                pass

            # 运行回测
            result = engine.run_backtest(config, benchmark_series=benchmark_series)
            formatted = engine.format_result(result)

            return {
                "success": True,
                "data": {
                    "result": result.model_dump(),
                    "formatted": formatted,
                },
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def compare_strategy_versions(
    strategy_a: str,
    strategy_b: str,
    days: int = 90,
    workspace: str = ".",
) -> dict:
    """对比两个策略版本的绩效"""
    try:
        return {
            "success": True,
            "data": {
                "message": f"策略对比功能待完善：{strategy_a} vs {strategy_b}",
                "strategy_a": strategy_a,
                "strategy_b": strategy_b,
                "days": days,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
