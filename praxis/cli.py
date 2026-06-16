"""PRAXIS CLI 入口"""
from __future__ import annotations

import os
import json
import click

from praxis.tools.portfolio import get_portfolio, get_asset_detail
from praxis.tools.market import get_market_data
from praxis.tools.engine import reconcile, check_constraints
from praxis.tools.ledger import get_ledger, add_transaction, reverse_transaction
from praxis.tools.state import get_state
from praxis.tools.decision import get_decision_record, list_decisions, create_decision
from praxis.tools.performance import get_performance
from praxis.tools.strategy import get_strategy, list_strategies
from praxis.tools.evolution import evaluate_evolution, evolve_strategy
from praxis.tools.benchmark import get_benchmark_data, list_benchmarks
from praxis.tools.nav import get_nav_snapshot, get_nav_history
from praxis.tools.ai_tracking import get_ai_tracking, format_tracking


# 获取工作目录
def get_workspace() -> str:
    return os.environ.get("PRAXIS_WORKSPACE", ".")


@click.group()
@click.version_option(version="v1.7.0")
def main():
    """PRAXIS - 投研纪律系统 CLI"""
    pass


@main.command()
def serve():
    """启动 MCP Server"""
    from praxis.mcp_server import mcp, _register_tools
    _register_tools()
    click.echo("启动 PRAXIS MCP Server...", err=True)
    mcp.run()


@main.group()
def portfolio():
    """组合管理"""
    pass


@portfolio.command("get")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
def portfolio_get(investor: str, portfolio: str):
    """读取组合配置"""
    result = get_portfolio(investor, portfolio, get_workspace())
    if result["success"]:
        click.echo(json.dumps(result["data"], ensure_ascii=False, indent=2))
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.command()
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
@click.option("--ticker", "-t", required=True, help="标的代码")
def asset(investor: str, portfolio: str, ticker: str):
    """读取标的详情"""
    result = get_asset_detail(investor, portfolio, ticker, get_workspace())
    if result["success"]:
        click.echo(json.dumps(result["data"], ensure_ascii=False, indent=2))
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.command("market")
@click.option("--tickers", "-t", required=True, help="标的代码列表（逗号分隔）")
def market_quote(tickers: str):
    """获取行情数据"""
    ticker_list = [t.strip() for t in tickers.split(",")]
    result = get_market_data(ticker_list)
    if result["success"]:
        click.echo(json.dumps(result["data"], ensure_ascii=False, indent=2))
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.command()
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
@click.option("--nav", "-n", type=float, default=None, help="场外基金净值")
@click.option("--dry-run/--no-dry-run", default=True, help="只读模式")
def reconcile_cmd(investor: str, portfolio: str, nav: float | None, dry_run: bool):
    """对账计算"""
    result = reconcile(investor, portfolio, nav, get_workspace())
    if result["success"]:
        click.echo(result["data"]["formatted"])
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.command("constraints")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
@click.option("--action", "-a", required=True, help="操作类型")
@click.option("--ticker", "-t", required=True, help="标的代码")
@click.option("--amount", type=float, default=0, help="交易金额")
def constraints_check(investor: str, portfolio: str, action: str, ticker: str, amount: float):
    """检查约束"""
    result = check_constraints(investor, portfolio, action, ticker, amount, get_workspace())
    if result["success"]:
        data = result["data"]
        click.echo(f"约束检查结果: {'通过' if data['all_passed'] else '未通过'}")
        for check in data["checks"]:
            status = "✓" if check["passed"] else "✗"
            click.echo(f"  {status} [{check['level']}] {check['rule']}: {check['message']}")
        if data["blocked"]:
            click.echo(f"\n阻止原因: {[b['message'] for b in data['blocked']]}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.command("state")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
def state_get(investor: str, portfolio: str):
    """从 ledger 重建组合状态"""
    result = get_state(investor, portfolio, get_workspace())
    if result["success"]:
        click.echo(result["data"]["formatted"])
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.group()
def ledger():
    """交易账本"""
    pass


@ledger.command("list")
@click.option("--ticker", "-t", default=None, help="标的代码（可选）")
@click.option("--limit", "-l", default=20, help="返回数量")
def ledger_list(ticker: str | None, limit: int):
    """查询交易记录"""
    result = get_ledger(ticker=ticker, limit=limit, workspace=get_workspace())
    if result["success"]:
        data = result["data"]
        click.echo(f"交易总数: {data['total']}")
        for tx in data["transactions"]:
            click.echo(
                f"  {tx['tx_id']} | {tx['type']:>10} | {tx['ticker']} | "
                f"{tx['quantity']}@{tx['price']} | fee={tx['fee']} | {tx['status']}"
            )
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@ledger.command("add")
@click.option("--ticker", "-t", required=True, help="标的代码")
@click.option("--action", "-a", required=True, help="操作类型")
@click.option("--quantity", "-q", required=True, type=float, help="数量")
@click.option("--price", "-p", required=True, type=float, help="价格")
@click.option("--fee", type=float, default=0, help="手续费")
@click.option("--auto-approve", is_flag=True, help="自动审批")
def ledger_add(ticker: str, action: str, quantity: float, price: float, fee: float, auto_approve: bool):
    """添加交易记录"""
    result = add_transaction(
        ticker=ticker, action=action, quantity=quantity, price=price,
        fee=fee, auto_approve=auto_approve, workspace=get_workspace(),
    )
    if result["success"]:
        data = result["data"]
        click.echo(f"状态: {data['status']}")
        click.echo(f"交易ID: {data['tx_id']}")
        click.echo(f"消息: {data['message']}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@ledger.command("reverse")
@click.option("--tx-id", required=True, help="要冲销的交易ID")
@click.option("--reason", required=True, help="冲销原因")
def ledger_reverse(tx_id: str, reason: str):
    """反向冲销交易"""
    result = reverse_transaction(tx_id, reason, get_workspace())
    if result["success"]:
        data = result["data"]
        click.echo(f"冲销成功")
        click.echo(f"原交易: {data['original_tx_id']}")
        click.echo(f"冲销记录: {data['correction_tx_id']}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.group()
def decision():
    """决策记录"""
    pass


@decision.command("get")
@click.option("--decision-id", "-d", required=True, help="决策ID")
def decision_get(decision_id: str):
    """获取决策记录"""
    result = get_decision_record(decision_id, get_workspace())
    if result["success"]:
        click.echo(json.dumps(result["data"], ensure_ascii=False, indent=2))
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@decision.command("list")
@click.option("--status", "-s", default=None, help="状态过滤")
@click.option("--limit", "-l", default=20, help="返回数量")
def decision_list(status: str | None, limit: int):
    """列出决策记录"""
    result = list_decisions(status=status, limit=limit, workspace=get_workspace())
    if result["success"]:
        data = result["data"]
        click.echo(f"决策总数: {data['total']}")
        for d in data["decisions"]:
            click.echo(
                f"  {d['decision_id']} | {d['action']:>10} | {d['ticker']} | "
                f"conf={d['confidence']:.2f} | {d['status']}"
            )
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@decision.command("create")
@click.option("--ticker", "-t", required=True, help="标的代码")
@click.option("--action", "-a", required=True, help="操作类型")
@click.option("--confidence", "-c", required=True, type=float, help="信心度")
@click.option("--reasoning", "-r", required=True, help="决策理由")
def decision_create(ticker: str, action: str, confidence: float, reasoning: str):
    """创建决策记录"""
    result = create_decision(
        ticker=ticker, action=action, confidence=confidence,
        reasoning=reasoning, workspace=get_workspace(),
    )
    if result["success"]:
        data = result["data"]
        click.echo(f"决策ID: {data['decision_id']}")
        click.echo(f"状态: {data['status']}")
        click.echo(f"消息: {data['message']}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.command("performance")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
def performance_get(investor: str, portfolio: str):
    """计算绩效指标（含基准对比）"""
    import asyncio
    result = asyncio.run(get_performance(investor, portfolio, get_workspace()))
    if result["success"]:
        click.echo(result["data"]["formatted"])
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.command("validate")
def validate_configs():
    """验证所有配置文件"""
    from praxis.core.config_validator import ConfigValidator
    results = ConfigValidator.validate_all_configs(get_workspace())
    report = ConfigValidator.format_validation_report(results)
    click.echo(report)

    # 如果有错误，返回非零退出码
    total_errors = sum(len(errors) for errors in results.values())
    if total_errors > 0:
        raise SystemExit(1)


@main.command("backtest")
@click.option("--strategy", "-s", required=True, help="策略名称")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
@click.option("--days", "-d", default=90, help="回测天数")
def backtest_cmd(strategy: str, investor: str, portfolio: str, days: int):
    """运行策略回测"""
    import asyncio
    from praxis.tools.backtest import run_backtest
    result = asyncio.run(run_backtest(strategy, investor, portfolio, days, get_workspace()))
    if result["success"]:
        click.echo(result["data"]["formatted"])
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.group()
def strategy():
    """策略管理"""
    pass


@strategy.command("get")
@click.option("--name", "-n", required=True, help="策略名称")
def strategy_get(name: str):
    """获取策略详情"""
    result = get_strategy(name, get_workspace())
    if result["success"]:
        data = result["data"]
        click.echo(f"策略: {data['name']}")
        click.echo(f"描述: {data['description']}")
        click.echo(f"\n规则 ({len(data['rules'])} 条):")
        for rule in data["rules"]:
            click.echo(f"  - {rule['rule']}")
        click.echo(f"\nAI 团队:")
        for team_name, team_config in data["ai_teams"].items():
            emphasis = team_config.get("emphasis", [])
            if emphasis:
                click.echo(f"  {team_name}: {', '.join(emphasis)}")
        click.echo(f"\n进化维度 ({len(data['evolution_dimensions'])} 个):")
        for dim in data["evolution_dimensions"]:
            click.echo(f"  - {dim['name']}: {dim['desc']}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@strategy.command("list")
def strategy_list():
    """列出所有策略"""
    result = list_strategies(get_workspace())
    if result["success"]:
        strategies = result["data"]["strategies"]
        click.echo(f"策略数量: {len(strategies)}")
        for s in strategies:
            click.echo(f"  - {s}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.group()
def evolution():
    """进化引擎"""
    pass


@evolution.command("evaluate")
@click.option("--strategy", "-s", required=True, help="策略名称")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
def evolution_evaluate(strategy: str, investor: str, portfolio: str):
    """评估进化维度"""
    result = evaluate_evolution(strategy, investor, portfolio, get_workspace())
    if result["success"]:
        click.echo(result["data"]["formatted"])
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@evolution.command("evolve")
@click.option("--strategy", "-s", required=True, help="策略名称")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
def evolution_evolve(strategy: str, investor: str, portfolio: str):
    """进化策略（需审批）"""
    result = evolve_strategy(strategy, investor, portfolio, get_workspace())
    if result["success"]:
        data = result["data"]
        click.echo(f"状态: {data['status']}")
        click.echo(f"备份: {data['backup_path']}")
        click.echo(f"消息: {data['message']}")
        click.echo(f"\n评估结果:")
        click.echo(data["evaluation"]["formatted"])
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.group()
def benchmark():
    """基准指数"""
    pass


@benchmark.command("list")
def benchmark_list():
    """列出支持的基准指数"""
    result = list_benchmarks()
    if result["success"]:
        for b in result["data"]["benchmarks"]:
            click.echo(f"  {b['code']} - {b['name']}: {b['description']}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@benchmark.command("get")
@click.option("--code", "-c", required=True, help="指数代码")
@click.option("--days", "-d", default=60, help="获取天数")
def benchmark_get(code: str, days: int):
    """获取基准指数数据"""
    result = get_benchmark_data(code, days)
    if result["success"]:
        data = result["data"]
        click.echo(f"指数: {data['index_code']}")
        click.echo(f"最新价格: {data['latest']['price']}")
        click.echo(f"涨跌幅: {data['latest']['change_pct']:.2f}%")
        click.echo(f"K线数据: {data['kline_count']} 条")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.group()
def nav():
    """净值追踪"""
    pass


@nav.command("snapshot")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
def nav_snapshot(investor: str, portfolio: str):
    """获取净值快照"""
    result = get_nav_snapshot(investor, portfolio, get_workspace())
    if result["success"]:
        data = result["data"]
        click.echo(f"日期: {data['date']}")
        click.echo(f"净值: {data['nav']:.4f}")
        click.echo(f"总资产: ¥{data['total_assets']:,.2f}")
        click.echo(f"持仓市值: ¥{data['positions_value']:,.2f}")
        click.echo(f"现金: ¥{data['cash']:,.2f}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@nav.command("history")
@click.option("--investor", "-i", required=True, help="投资者ID")
@click.option("--portfolio", "-p", required=True, help="组合ID")
@click.option("--days", "-d", default=30, help="获取天数")
def nav_history(investor: str, portfolio: str, days: int):
    """获取净值历史"""
    result = get_nav_history(investor, portfolio, days, get_workspace())
    if result["success"]:
        data = result["data"]
        click.echo(f"记录总数: {data['total']}")
        for nav in data["history"]:
            click.echo(f"  {nav['date']}: {nav['nav']:.4f}")
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


@main.command("ai-tracking")
@click.option("--team", "-t", default=None, help="团队名称（asrg/masters/trading）")
def ai_tracking(team: str):
    """获取 AI 建议命中率"""
    result = get_ai_tracking(team, get_workspace())
    if result["success"]:
        click.echo(format_tracking(result["data"]))
    else:
        click.echo(f"错误: {result['error']}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
