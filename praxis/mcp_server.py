"""PRAXIS MCP Server 入口"""
from __future__ import annotations

import asyncio
import os
import time
from mcp.server.fastmcp import FastMCP

from praxis.tools.portfolio import get_portfolio, get_asset_detail
from praxis.tools.market import get_market_data
from praxis.tools.engine import reconcile, check_constraints
from praxis.tools.ledger import get_ledger, add_transaction, approve_transaction, reverse_transaction, delete_transaction, purge_ledger, reject_transaction, list_pending_transactions
from praxis.tools.state import get_state
from praxis.tools.decision import get_decision_record, list_decisions, create_decision
from praxis.tools.performance import get_performance
from praxis.tools.strategy import get_strategy, list_strategies, update_portfolio
from praxis.tools.evolution import evaluate_evolution, evolve_strategy
from praxis.tools.benchmark import get_benchmark_data, list_benchmarks
from praxis.tools.nav import record_nav, get_nav_snapshot, get_nav_history
from praxis.tools.ai_tracking import get_ai_tracking
from praxis.tools.teams import list_teams, get_team_prompt, compose_team_prompt, list_output_templates, get_output_template, update_output_template, approve_output_template_update, create_output_template
from praxis.tools.review import fill_reviews, get_review_summary, get_confidence_calibration
from praxis.tools.backtest import run_backtest, compare_strategy_versions
from praxis.tools.version_compare import compare_versions
from praxis.tools.grayscale import prepare_grayscale, approve_grayscale
from praxis.tools.friction import calculate_fee, calculate_slippage, check_trading_time, get_confirm_date
from praxis.tools.data_quality import check_quote_quality, clean_quote_data, get_quality_report
from praxis.tools.prompt_versioning import list_prompt_versions, get_prompt_version, create_prompt_version, rollback_prompt, check_prompt_safety, get_version_diff
from praxis.tools.investor import create_investor, create_portfolio, init_investor
from praxis.tools.summary import get_portfolio_summary
from praxis.tools.workspace import discover_workspace
from praxis.core.logger import get_logger, init_logger

# 创建 MCP Server
mcp = FastMCP("PRAXIS", json_response=True)

# 获取工作目录
WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", ".")

# 初始化日志
init_logger(log_dir=os.path.join(WORKSPACE, "data", "logs"))


async def _log_tool_call(tool_name: str, func, *args, **kwargs):
    """记录工具调用的辅助函数"""
    logger = get_logger()
    start_time = time.time()
    try:
        result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.tool_call(
            tool_name=tool_name,
            parameters=kwargs,
            success=result.get("success", True),
            duration_ms=duration_ms,
            error=result.get("error"),
        )
        return result
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.tool_call(
            tool_name=tool_name,
            parameters=kwargs,
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_portfolio_tool(investor: str, portfolio: str) -> dict:
    """读取投资组合配置
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return await _log_tool_call("get_portfolio", get_portfolio, investor=investor, portfolio=portfolio, workspace=WORKSPACE)


@mcp.tool()
async def get_asset_detail_tool(investor: str, portfolio: str, ticker: str) -> dict:
    """读取单个标的详情
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return await _log_tool_call("get_asset_detail", get_asset_detail, investor=investor, portfolio=portfolio, ticker=ticker, workspace=WORKSPACE)


@mcp.tool()
async def get_market_data_tool(tickers: list[str]) -> dict:
    """获取实时行情数据"""
    return await get_market_data(tickers)


@mcp.tool()
async def reconcile_tool(investor: str, portfolio: str, nav: float | None = None) -> dict:
    """对账计算（dry-run 模式）
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return await reconcile(investor, portfolio, nav, WORKSPACE)


@mcp.tool()
async def check_constraints_tool(investor: str, portfolio: str, action: str, ticker: str, amount: float = 0) -> dict:
    """检查交易约束
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return check_constraints(investor, portfolio, action, ticker, amount, WORKSPACE)


@mcp.tool()
async def get_state_tool(investor: str, portfolio: str, infer_from_ledger: bool = False) -> dict:
    """从 ledger 重建组合状态

    Args:
        investor: 投资者 ID
        portfolio: 组合 ID
        infer_from_ledger: 纯 ledger 推断模式（不需要配置文件，适合初始化阶段）
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return await get_state(investor, portfolio, infer_from_ledger, WORKSPACE)


@mcp.tool()
async def get_ledger_tool(ticker: str | None = None, limit: int = 100) -> dict:
    """查询交易记录"""
    return get_ledger(ticker=ticker, limit=limit, workspace=WORKSPACE)


@mcp.tool()
async def add_transaction_tool(
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    fee: float = 0,
    decision_id: str | None = None,
    idempotency_key: str | None = None,
    auto_approve: bool = False,
    tags: list[str] | None = None,
    asset_type: str | None = None,
) -> dict:
    """添加交易记录（需审批）

    Args:
        ticker: 标的代码
        action: 操作类型（buy/sell/subscribe/redeem/dividend）
        quantity: 数量
        price: 价格
        fee: 手续费
        decision_id: 关联决策ID
        idempotency_key: 幂等键（防重复）
        auto_approve: 自动审批（跳过审批流程）
        tags: 标签列表（如 ["test"] ["migration"] ["real"]），绩效计算时可按标签过滤
        asset_type: 资产类型（stock/etf/offshore_fund），用于策略规则精确匹配
    """
    return add_transaction(
        ticker=ticker, action=action, quantity=quantity, price=price,
        fee=fee, decision_id=decision_id, idempotency_key=idempotency_key,
        auto_approve=auto_approve, tags=tags, asset_type=asset_type,
        workspace=WORKSPACE,
    )


@mcp.tool()
async def reverse_transaction_tool(tx_id: str, reason: str) -> dict:
    """反向冲销交易"""
    return reverse_transaction(tx_id, reason, WORKSPACE)


@mcp.tool()
async def delete_transaction_tool(tx_id: str) -> dict:
    """物理删除单条交易记录（仅用于清理测试/错误数据）

    警告：破坏 append-only 语义，正常业务请使用 reverse_transaction_tool。
    """
    return delete_transaction(tx_id, WORKSPACE)


@mcp.tool()
async def purge_ledger_tool(tag: str | None = None, confirm: bool = False) -> dict:
    """清空交易账本（按标签或全部）

    Args:
        tag: 如果指定，仅删除带有该标签的记录；None 则清空全部
        confirm: 必须为 True 才执行（安全确认）
    """
    return purge_ledger(tag, confirm, WORKSPACE)


@mcp.tool()
async def approve_transaction_tool(tx_id: str) -> dict:
    """审批通过待审批交易（从 pending 写入正式账本）

    Args:
        tx_id: 待审批交易的 ID（格式: tx-YYYYMMDD-pending-NNN）
    """
    return approve_transaction(tx_id, WORKSPACE)


@mcp.tool()
async def reject_transaction_tool(tx_id: str, reason: str) -> dict:
    """拒绝待审批交易

    Args:
        tx_id: 待审批交易的 ID
        reason: 拒绝原因
    """
    return reject_transaction(tx_id, reason, WORKSPACE)


@mcp.tool()
async def list_pending_transactions_tool() -> dict:
    """列出所有待审批的交易"""
    return list_pending_transactions(WORKSPACE)


@mcp.tool()
async def get_portfolio_summary_tool(investor: str, portfolio: str) -> dict:
    """获取组合聚合概览（一次返回总资产/持仓/配置比/交易统计）

    避免需要调用 4-5 个工具才能拼出完整视图。

    Args:
        investor: 投资者 ID
        portfolio: 组合 ID
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return await get_portfolio_summary(investor, portfolio, WORKSPACE)


@mcp.tool()
async def get_decision_record_tool(decision_id: str) -> dict:
    """获取决策记录"""
    return get_decision_record(decision_id, WORKSPACE)


@mcp.tool()
async def list_decisions_tool(status: str | None = None, limit: int = 50) -> dict:
    """列出决策记录"""
    return list_decisions(status=status, limit=limit, workspace=WORKSPACE)


@mcp.tool()
async def create_decision_tool(
    ticker: str,
    action: str,
    confidence: float,
    reasoning: str,
    quantity: float | None = None,
    price_range: list[float] | None = None,
) -> dict:
    """创建决策记录"""
    return create_decision(
        ticker=ticker, action=action, confidence=confidence,
        reasoning=reasoning, quantity=quantity, price_range=price_range,
        workspace=WORKSPACE,
    )


@mcp.tool()
async def get_performance_tool(
    investor: str,
    portfolio: str,
    exclude_reversed: bool = False,
    exclude_tags: list[str] | None = None,
    include_tags: list[str] | None = None,
    ticker: str | None = None,
) -> dict:
    """计算绩效指标（含基准对比）

    Args:
        investor: 投资者 ID
        portfolio: 组合 ID
        exclude_reversed: 排除已冲销的交易对（推荐开启以获得真实绩效）
        exclude_tags: 排除带有这些标签的交易（如 ["test", "migration"]）
        include_tags: 仅计算带有这些标签的交易（如 ["real"]）
        ticker: 仅计算指定标的的绩效（如 "600995"）
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return await get_performance(investor, portfolio, exclude_reversed, exclude_tags, include_tags, ticker, WORKSPACE)


@mcp.tool()
async def get_strategy_tool(strategy_name: str) -> dict:
    """获取策略详情"""
    return get_strategy(strategy_name, WORKSPACE)


@mcp.tool()
async def list_strategies_tool() -> dict:
    """列出所有策略模板"""
    return list_strategies(WORKSPACE)


@mcp.tool()
async def update_portfolio_tool(
    investor: str,
    portfolio: str,
    field: str,
    value: str,
) -> dict:
    """修改组合配置（需审批）
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return update_portfolio(investor, portfolio, field, value, WORKSPACE)


@mcp.tool()
async def evaluate_evolution_tool(
    strategy_name: str,
    investor: str,
    portfolio: str,
) -> dict:
    """评估进化维度
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return evaluate_evolution(strategy_name, investor, portfolio, WORKSPACE)


@mcp.tool()
async def evolve_strategy_tool(
    strategy_name: str,
    investor: str,
    portfolio: str,
) -> dict:
    """进化策略（需审批）
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return evolve_strategy(strategy_name, investor, portfolio, WORKSPACE)


@mcp.tool()
async def get_benchmark_data_tool(index_code: str, days: int = 60) -> dict:
    """获取基准指数数据"""
    return await get_benchmark_data(index_code, days)


@mcp.tool()
async def list_benchmarks_tool() -> dict:
    """列出支持的基准指数"""
    return list_benchmarks()


@mcp.tool()
async def record_nav_tool(
    investor: str,
    portfolio: str,
    nav: float,
    total_assets: float,
    positions_value: float,
    cash: float,
    benchmark_nav: float | None = None,
    benchmark_code: str | None = None,
) -> dict:
    """记录当日净值
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return record_nav(investor, portfolio, nav, total_assets, positions_value, cash, benchmark_nav, benchmark_code, WORKSPACE)


@mcp.tool()
async def get_nav_snapshot_tool(investor: str, portfolio: str) -> dict:
    """获取净值快照
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return await get_nav_snapshot(investor, portfolio, WORKSPACE)


@mcp.tool()
async def get_nav_history_tool(investor: str, portfolio: str, days: int = 30) -> dict:
    """获取净值历史
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return get_nav_history(investor, portfolio, days, WORKSPACE)


@mcp.tool()
async def get_ai_tracking_tool(team: str | None = None) -> dict:
    """获取 AI 建议命中率"""
    return get_ai_tracking(team, WORKSPACE)


@mcp.tool()
async def list_teams_tool() -> dict:
    """列出所有可用的 AI 团队（ASRG/大师圆桌/交易团队）"""
    return list_teams(WORKSPACE)


@mcp.tool()
async def get_team_prompt_tool(team_name: str) -> dict:
    """获取指定团队的完整 Prompt

    Args:
        team_name: 团队名称（asrg/masters/trading）

    Returns:
        团队 Prompt 内容
    """
    return get_team_prompt(team_name, WORKSPACE)


@mcp.tool()
async def compose_team_prompt_tool(
    team_name: str,
    strategy_name: str = "grid_value",
    investor_id: str = "example",
) -> dict:
    """组合团队 Prompt（基础 + 团队 + 策略 + 投资者）

    Args:
        team_name: 团队名称（asrg/masters/trading）
        strategy_name: 策略名称
        investor_id: 投资者ID

    Returns:
        组合后的完整 Prompt
    """
    return compose_team_prompt(team_name, strategy_name, investor_id, WORKSPACE)


@mcp.tool()
async def list_output_templates_tool() -> dict:
    """列出所有输出模板（ASRG/大师圆桌/交易团队/综合日报）"""
    return list_output_templates(WORKSPACE)


@mcp.tool()
async def get_output_template_tool(template_name: str) -> dict:
    """获取指定输出模板

    Args:
        template_name: 模板名称（asrg_output/masters_output/trading_output/daily_report）

    Returns:
        输出模板内容
    """
    return get_output_template(template_name, WORKSPACE)


@mcp.tool()
async def update_output_template_tool(
    template_name: str,
    new_content: str,
    reason: str,
) -> dict:
    """更新输出模板（需审批）

    Args:
        template_name: 模板名称
        new_content: 新的模板内容
        reason: 修改原因

    Returns:
        变更预览和备份信息
    """
    return update_output_template(template_name, new_content, reason, WORKSPACE)


@mcp.tool()
async def approve_output_template_update_tool(
    template_name: str,
    new_content: str,
) -> dict:
    """审批通过后执行模板更新

    Args:
        template_name: 模板名称
        new_content: 新的模板内容

    Returns:
        更新结果
    """
    return approve_output_template_update(template_name, new_content, WORKSPACE)


@mcp.tool()
async def create_output_template_tool(
    template_name: str,
    content: str,
) -> dict:
    """创建新的输出模板

    Args:
        template_name: 模板名称
        content: 模板内容

    Returns:
        创建结果
    """
    return create_output_template(template_name, content, WORKSPACE)


@mcp.tool()
async def fill_reviews_tool() -> dict:
    """自动回填待复盘的决策（5d/20d/60d）"""
    return await fill_reviews(WORKSPACE)


@mcp.tool()
async def get_review_summary_tool() -> dict:
    """获取复盘汇总（待复盘数量/已复盘数量）"""
    return get_review_summary(WORKSPACE)


@mcp.tool()
async def get_confidence_calibration_tool(team: str) -> dict:
    """获取指定团队的信心度校准误差

    Args:
        team: 团队名称（asrg/masters/trading）

    Returns:
        信心度校准结果
    """
    return get_confidence_calibration(team, WORKSPACE)


@mcp.tool()
async def run_backtest_tool(
    strategy_name: str,
    investor: str,
    portfolio: str,
    days: int = 90,
) -> dict:
    """运行策略回测

    Args:
        strategy_name: 策略名称
        investor: 投资者ID
        portfolio: 组合ID
        days: 回测天数

    Returns:
        回测结果
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    return await run_backtest(strategy_name, investor, portfolio, days, WORKSPACE)


@mcp.tool()
async def compare_strategy_versions_tool(
    strategy_a: str,
    strategy_b: str,
    days: int = 90,
) -> dict:
    """对比两个策略版本的绩效

    Args:
        strategy_a: 策略A名称
        strategy_b: 策略B名称
        days: 对比天数

    Returns:
        策略对比结果
    """
    return await compare_strategy_versions(strategy_a, strategy_b, days, WORKSPACE)


@mcp.tool()
async def compare_versions_tool(
    strategy_a: str,
    strategy_b: str,
) -> dict:
    """对比两个策略版本的绩效指标

    Args:
        strategy_a: 策略A名称
        strategy_b: 策略B名称

    Returns:
        策略版本对比结果
    """
    return await compare_versions(strategy_a, strategy_b, WORKSPACE)


@mcp.tool()
async def prepare_grayscale_tool(
    strategy_name: str,
    change_description: str,
    risk_level: str = "medium",
    validation_days: int = 30,
) -> dict:
    """准备策略灰度验证

    Args:
        strategy_name: 策略名称
        change_description: 变更描述
        risk_level: 风险等级（low/medium/high）
        validation_days: 验证天数

    Returns:
        灰度验证结果
    """
    return prepare_grayscale(strategy_name, change_description, risk_level, validation_days, WORKSPACE)


@mcp.tool()
async def approve_grayscale_tool(
    strategy_name: str,
    backup_path: str,
    new_content: str,
) -> dict:
    """审批通过后应用策略变更

    Args:
        strategy_name: 策略名称
        backup_path: 备份文件路径
        new_content: 新的策略内容

    Returns:
        应用结果
    """
    return approve_grayscale(strategy_name, backup_path, new_content, WORKSPACE)


@mcp.tool()
async def calculate_fee_tool(
    ticker: str,
    asset_type: str,
    action: str,
    quantity: float,
    price: float,
) -> dict:
    """计算交易费用

    Args:
        ticker: 标的代码
        asset_type: 资产类型（stock/etf/offshore_fund）
        action: 操作类型（buy/sell/subscribe/redeem）
        quantity: 数量
        price: 价格

    Returns:
        费用明细
    """
    return calculate_fee(ticker, asset_type, action, quantity, price, WORKSPACE)


@mcp.tool()
async def calculate_slippage_tool(
    price: float,
    action: str,
    volume: float | None = None,
    volatility: float | None = None,
) -> dict:
    """计算滑点

    Args:
        price: 委托价格
        action: 操作类型（buy/sell）
        volume: 成交量（可选）
        volatility: 波动率（可选）

    Returns:
        滑点明细
    """
    return calculate_slippage(price, action, volume, volatility, WORKSPACE)


@mcp.tool()
async def check_trading_time_tool(
    timestamp: str | None = None,
    asset_type: str = "stock",
) -> dict:
    """检查交易时间

    Args:
        timestamp: 时间戳（ISO 格式，可选，默认当前时间）
        asset_type: 资产类型（stock/etf/offshore_fund）

    Returns:
        交易时间信息
    """
    return check_trading_time(timestamp, asset_type, WORKSPACE)


@mcp.tool()
async def get_confirm_date_tool(
    trade_date: str,
    asset_type: str = "stock",
) -> dict:
    """获取确认日期

    Args:
        trade_date: 交易日期（YYYY-MM-DD）
        asset_type: 资产类型（stock/etf/offshore_fund）

    Returns:
        确认日期
    """
    return get_confirm_date(trade_date, asset_type, WORKSPACE)


@mcp.tool()
async def check_quote_quality_tool(
    ticker: str,
    data: dict,
) -> dict:
    """检查行情数据质量

    Args:
        ticker: 标的代码
        data: 行情数据

    Returns:
        质量检查结果
    """
    return check_quote_quality(ticker, data, WORKSPACE)


@mcp.tool()
async def clean_quote_data_tool(
    ticker: str,
    data: dict,
) -> dict:
    """清洗行情数据

    Args:
        ticker: 标的代码
        data: 原始行情数据

    Returns:
        清洗后的数据
    """
    return clean_quote_data(ticker, data, WORKSPACE)


@mcp.tool()
async def get_quality_report_tool() -> dict:
    """获取数据质量报告

    Returns:
        质量报告
    """
    return get_quality_report(WORKSPACE)


@mcp.tool()
async def list_prompt_versions_tool(
    prompt_name: str,
) -> dict:
    """列出 Prompt 的所有版本

    Args:
        prompt_name: Prompt 名称

    Returns:
        版本列表
    """
    return list_prompt_versions(prompt_name, WORKSPACE)


@mcp.tool()
async def get_prompt_version_tool(
    prompt_name: str,
    version: str | None = None,
) -> dict:
    """获取指定版本的 Prompt

    Args:
        prompt_name: Prompt 名称
        version: 版本号（可选，默认获取最新活动版本）

    Returns:
        Prompt 内容
    """
    return get_prompt_version(prompt_name, version, WORKSPACE)


@mcp.tool()
async def create_prompt_version_tool(
    prompt_name: str,
    content: str,
    description: str | None = None,
) -> dict:
    """创建新版本

    Args:
        prompt_name: Prompt 名称
        content: Prompt 内容
        description: 版本描述

    Returns:
        新版本信息
    """
    return create_prompt_version(prompt_name, content, description, WORKSPACE)


@mcp.tool()
async def rollback_prompt_tool(
    prompt_name: str,
    target_version: str,
    reason: str,
) -> dict:
    """回滚到指定版本

    Args:
        prompt_name: Prompt 名称
        target_version: 目标版本
        reason: 回滚原因

    Returns:
        回滚后的版本信息
    """
    return rollback_prompt(prompt_name, target_version, reason, WORKSPACE)


@mcp.tool()
async def check_prompt_safety_tool(
    content: str,
) -> dict:
    """检查 Prompt 安全性

    Args:
        content: Prompt 内容

    Returns:
        安全检查结果
    """
    return check_prompt_safety(content, WORKSPACE)


@mcp.tool()
async def get_version_diff_tool(
    prompt_name: str,
    from_version: str,
    to_version: str,
) -> dict:
    """获取版本差异

    Args:
        prompt_name: Prompt 名称
        from_version: 起始版本
        to_version: 目标版本

    Returns:
        差异信息
    """
    return get_version_diff(prompt_name, from_version, to_version, WORKSPACE)


@mcp.tool()
async def create_investor_tool(
    investor_id: str,
    name: str,
    capital_cny: float,
    risk_level: str = "C3",
    style: str = "balanced",
    max_drawdown_pct: float = 20,
) -> dict:
    """创建投资者画像配置文件（解决配置文件不存在的死循环）

    Args:
        investor_id: 投资者 ID（目录名）
        name: 投资者名称
        capital_cny: 初始资金（人民币）
        risk_level: 风险等级（C1-C5）
        style: 投资风格
        max_drawdown_pct: 最大回撤容忍度(%)
    """
    return create_investor(investor_id, name, capital_cny, risk_level, style, max_drawdown_pct, WORKSPACE)


@mcp.tool()
async def create_portfolio_tool(
    investor_id: str,
    portfolio_id: str,
    strategy_type: str = "grid_value",
    strategy_template: str = "grid_value",
    description: str | None = None,
    assets: list[dict] | None = None,
) -> dict:
    """创建投资组合配置文件

    Args:
        investor_id: 投资者 ID
        portfolio_id: 组合 ID（目录名）
        strategy_type: 策略类型
        strategy_template: 策略模板名称
        description: 组合描述
        assets: 资产列表 [{ticker, name, type, category, target_weight_pct}]
    """
    return create_portfolio(investor_id, portfolio_id, strategy_type, strategy_template, description, assets, WORKSPACE)


@mcp.tool()
async def init_investor_tool(
    investor_id: str,
    investor_name: str,
    capital_cny: float,
    portfolio_id: str,
    positions: list[dict],
    cash: float,
    risk_level: str = "C3",
    style: str = "balanced",
    max_drawdown_pct: float = 20,
    strategy_type: str = "grid_value",
    strategy_template: str = "grid_value",
    benchmark: str | None = None,
) -> dict:
    """一条命令完成投资者+组合+持仓初始化

    自动创建 profile.yaml + portfolio.yaml + 写入 opening positions 到 ledger。

    Args:
        investor_id: 投资者 ID
        investor_name: 投资者名称
        capital_cny: 初始总资金
        portfolio_id: 组合 ID
        positions: 持仓列表 [{ticker, name, quantity, avg_cost, type, category}]
        cash: 当前现金余额
        risk_level: 风险等级
        style: 投资风格
        max_drawdown_pct: 最大回撤容忍度(%)
        strategy_type: 策略类型
        strategy_template: 策略模板名称
        benchmark: 基准指数代码（可选）
    """
    return init_investor(
        investor_id, investor_name, capital_cny, portfolio_id, positions, cash,
        risk_level, style, max_drawdown_pct, strategy_type, strategy_template,
        benchmark, WORKSPACE,
    )


@mcp.tool()
async def discover_workspace_tool() -> dict:
    """发现 workspace 全景：投资者、组合、持仓、数据状态、推荐下一步操作。
    零参数，首次连接时调用。"""
    return discover_workspace(WORKSPACE)


@mcp.resource("praxis://workspace/discovery")
def workspace_discovery_resource() -> dict:
    """Workspace 元数据（MCP Resource）：支持 Resources 协议的客户端可在连接握手时自动读取。"""
    return discover_workspace(WORKSPACE)


def main():
    """启动 MCP Server"""
    mcp.run()


if __name__ == "__main__":
    main()
