"""MCP 工具 - 绩效指标"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.engine.performance import EnhancedPerformanceCalculator
from praxis.engine.data.benchmark import TencentBenchmarkProvider


async def get_performance(
    investor: str,
    portfolio: str,
    exclude_reversed: bool = False,
    exclude_tags: list[str] | None = None,
    include_tags: list[str] | None = None,
    ticker: str | None = None,
    workspace: str = ".",
) -> dict:
    """计算绩效指标（含基准对比）

    Args:
        exclude_reversed: 排除已冲销的交易对
        exclude_tags: 排除带有这些标签的交易
        include_tags: 仅计算带有这些标签的交易
        ticker: 仅计算指定标的的绩效
    """
    try:
        ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
        ledger = FileLedger(ledger_path)

        # 加载投资者的实际初始资金
        from praxis.engine.config_loader import YamlConfigLoader
        loader = YamlConfigLoader(workspace)
        try:
            inv = loader.load_investor(investor)
            initial_capital = inv.capital_cny
        except Exception:
            initial_capital = 70000

        calculator = EnhancedPerformanceCalculator(ledger, initial_capital=initial_capital)

        # 获取基准数据（沪深300）
        benchmark_return = None
        try:
            provider = TencentBenchmarkProvider()
            end_date = datetime.now().strftime("%Y-%m-%d")
            # 获取最近 60 天的基准数据
            start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
            kline = await provider.get_daily_kline("000300", start_date, end_date)
            if kline and len(kline) >= 2:
                benchmark_return = (kline[-1]["close"] - kline[0]["open"]) / kline[0]["open"]
            await provider.close()
        except Exception:
            pass  # 基准数据获取失败不影响主计算

        metrics = calculator.calculate(
            investor, portfolio,
            exclude_reversed=exclude_reversed,
            exclude_tags=exclude_tags,
            include_tags=include_tags,
            ticker=ticker,
        )

        # 计算超额收益
        excess_return = None
        if benchmark_return is not None:
            excess_return = metrics.total_return - benchmark_return

        # 格式化输出
        scope_desc = ""
        if ticker:
            scope_desc = f"（标的: {ticker}）"
        elif exclude_reversed:
            scope_desc = "（已排除冲销记录）"
        elif exclude_tags:
            scope_desc = f"（已排除标签: {', '.join(exclude_tags)}）"
        elif include_tags:
            scope_desc = f"（仅含标签: {', '.join(include_tags)}）"

        lines = [
            f"=== 绩效指标{scope_desc} ===",
            f"投资者: {investor}",
            f"组合: {portfolio}",
            f"",
            f"--- 收益指标 ---",
            f"总收益率: {metrics.total_return:.2%}",
            f"年化收益率: {metrics.annualized_return:.2%}",
            f"已实现盈亏: ¥{metrics.realized_pnl:,.2f}",
        ]

        if benchmark_return is not None:
            lines.append(f"基准收益（沪深300）: {benchmark_return:.2%}")
            if excess_return is not None:
                lines.append(f"超额收益: {excess_return:.2%} {'✅ 跑赢基准' if excess_return > 0 else '❌ 跑输基准'}")

        lines.extend([
            f"",
            f"--- 风险指标 ---",
            f"最大回撤: {metrics.max_drawdown:.2%}",
            f"年化波动率: {metrics.volatility:.2%}",
            f"夏普比率: {metrics.sharpe_ratio:.2f}",
            f"卡玛比率: {metrics.calmar_ratio:.2f}",
            f"",
            f"--- 交易统计 ---",
            f"买入次数: {metrics.buy_count}",
            f"卖出次数: {metrics.sell_count}",
            f"胜率: {metrics.win_rate:.1%}",
            f"盈亏比: {metrics.profit_loss_ratio:.2f}",
            f"换手率: {metrics.turnover_rate:.2f}",
            f"总手续费: ¥{metrics.total_fee:,.2f}",
            f"分红收入: ¥{metrics.total_dividend:,.2f}",
        ])

        return {
            "success": True,
            "data": {
                "metrics": metrics.model_dump(),
                "benchmark_return": benchmark_return,
                "excess_return": excess_return,
                "formatted": "\n".join(lines),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
