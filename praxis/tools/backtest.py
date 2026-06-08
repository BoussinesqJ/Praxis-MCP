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
) -> dict:
    """运行策略回测"""
    try:
        ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
        ledger = FileLedger(ledger_path)
        engine = SimpleBacktestEngine(ledger)

        # 计算回测期间
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

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
    """对比两个策略版本的绩效

    注意：当前为存根实现。需要分别加载两个策略的交易历史并计算绩效指标。
    后续版本将实现基于策略版本标记的绩效对比。
    """
    try:
        from praxis.tools.strategy import get_strategy
        a_data = get_strategy(strategy_a, workspace)
        b_data = get_strategy(strategy_b, workspace)

        if not a_data.get("success"):
            return {"success": False, "error": f"策略 {strategy_a} 不存在"}
        if not b_data.get("success"):
            return {"success": False, "error": f"策略 {strategy_b} 不存在"}

        return {
            "success": True,
            "data": {
                "status": "stub",
                "message": f"策略对比功能待完善：{strategy_a} vs {strategy_b}。需要带版本标记的历史净值数据。",
                "strategy_a": {
                    "name": strategy_a,
                    "rules_count": len(a_data["data"].get("rules", [])),
                },
                "strategy_b": {
                    "name": strategy_b,
                    "rules_count": len(b_data["data"].get("rules", [])),
                },
                "days": days,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
