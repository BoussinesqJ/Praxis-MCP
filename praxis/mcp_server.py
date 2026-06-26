"""PRAXIS MCP Server v3.5 — 级联复盘 + 单工具链式调用

v3.5: 级联复盘体系（monthly/quarterly/annual）+ 单工具链式调用
v3.3: 引入 stdout 物理隔离，防止第三方库 print() 污染 MCP JSON 管道
v3.2: 修复 asyncio 事件循环阻塞 + 串行调用约束
底层 praxis/tools/*.py 零改动，仅重构本文件的 facade 层。
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time
from mcp.server.fastmcp import FastMCP

# ─── 全局抑制第三方网络噪音 ───────────────────────────────────────
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("akshare").setLevel(logging.WARNING)
logging.getLogger("ak").setLevel(logging.WARNING)

# ─── 全局 CachedDataProvider 单例（避免每次工具调用都 auto_discover） ─
_GLOBAL_PROVIDER: CachedDataProvider | None = None


async def get_global_provider() -> CachedDataProvider:
    """获取全局共享的 CachedDataProvider 实例（懒初始化）"""
    global _GLOBAL_PROVIDER
    if _GLOBAL_PROVIDER is None:
        from praxis.engine.data.provider import CachedDataProvider

        _GLOBAL_PROVIDER = CachedDataProvider(workspace=WORKSPACE)
    return _GLOBAL_PROVIDER


async def close_global_provider():
    """关闭全局 provider（服务退出时调用）"""
    global _GLOBAL_PROVIDER
    if _GLOBAL_PROVIDER is not None:
        await _GLOBAL_PROVIDER.close()
        _GLOBAL_PROVIDER = None
os.environ.setdefault("NO_PROXY", "*")

# ─── 安全线程包装器 (Stdio 隔离核心) ─────────────────────────────
def _safe_sync_runner(func, *args, **kwargs):
    """在独立线程中运行同步函数，并强制将标准输出隔离到 stderr，保护 MCP JSON 管道"""
    with contextlib.redirect_stdout(sys.stderr):
        return func(*args, **kwargs)


# ─── 超时包装器 (防止 MCP 卡死) ─────────────────────────────────
TOOL_TIMEOUT_SECONDS = 15  # 工具调用超时


async def run_in_safe_thread(func, *args, **kwargs):
    """安全包装器：卸载到线程，切断 stdout 污染，并添加超时保护"""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_safe_sync_runner, func, *args, **kwargs),
            timeout=TOOL_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return {"success": False, "error": f"工具调用超时 ({TOOL_TIMEOUT_SECONDS}s)"}

# ─── MCP Server 创建 ─────────────────────────────────────────────
mcp = FastMCP("PRAXIS", json_response=True)

# 获取工作目录
WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", ".")

# ─── Logger ──────────────────────────────────────────────────────
_logger_initialized = False


def _ensure_logger():
    global _logger_initialized
    if not _logger_initialized:
        from praxis.core.logger import init_logger
        init_logger(log_dir=os.path.join(WORKSPACE, "data", "logs"))
        _logger_initialized = True


async def _log_tool_call(tool_name: str, func, *args, **kwargs):
    """记录工具调用的辅助函数"""
    _ensure_logger()
    from praxis.core.logger import get_logger
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


# ═══════════════════════════════════════════════════════════════════
# 分层注册
# ═══════════════════════════════════════════════════════════════════

_TOOLS_TIER: dict[str, dict] = {
    # ── core（默认加载，日常监控 + 交易）──
    "discover_workspace_tool": {"tier": "core", "version": "3.5"},
    "get_portfolio_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "get_asset_detail_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "get_market_data_tool": {"tier": "core", "version": "3.5"},
    "get_state_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "get_portfolio_summary_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "get_performance_tool": {"tier": "core", "version": "3.5"},
    "reconcile_tool": {"tier": "core", "version": "3.5"},
    "check_constraints_tool": {"tier": "core", "version": "3.5"},
    "ledger_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "transaction_approval_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "decision_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "nav_tool": {"tier": "core", "version": "3.5"},
    "sentinel_tool": {"tier": "core", "version": "3.5"},
    "valuation_tool": {"tier": "core", "version": "3.5"},
    "sentiment_tool": {"tier": "core", "version": "3.5"},
    "news_tool": {"tier": "core", "version": "3.5"},
    "benchmark_tool": {"tier": "core", "version": "3.5"},
    "agent_tracking_tool": {"tier": "core", "version": "3.5"},
    "review_tool": {"tier": "core", "version": "3.5"},
    "trading_friction_tool": {"tier": "core", "version": "3.5"},
    # ── 数据源工具（新增）──
    "fund_flow_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "dragon_tiger_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    "research_report_tool": {"tier": "core", "version": "3.4", "deprecated": True},
    # ── v3.5 整合工具 (Consolidated Tools) ──
    "portfolio_tool": {"tier": "core", "version": "3.5"},
    "trading_tool": {"tier": "core", "version": "3.5"},
    "market_data_ext_tool": {"tier": "core", "version": "3.5"},
    "cascade_review_tool": {"tier": "core", "version": "3.5"},
    "strategy_tool": {"tier": "advanced", "version": "3.5"},
    "evolution_tool": {"tier": "advanced", "version": "3.5"},
    "grayscale_tool": {"tier": "advanced", "version": "3.5"},
    "team_tool": {"tier": "admin", "version": "3.5"},
    # ── advanced（策略进化、回测、灰度）──
    "evaluate_evolution_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "auto_evolve_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "run_backtest_tool": {"tier": "advanced", "version": "3.5"},
    "compare_versions_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "prepare_grayscale_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "approve_grayscale_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "get_strategy_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "list_strategies_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "update_portfolio_tool": {"tier": "advanced", "version": "3.5"},
    "evolution_memory_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "adaptive_rules_tool": {"tier": "advanced", "version": "3.4", "deprecated": True},
    "orchestrator_tool": {"tier": "advanced", "version": "3.5"},
    # ── admin（投资者初始化、团队/Prompt 配置、数据质量）──
    "investor_tool": {"tier": "admin", "version": "3.5"},
    "team_config_tool": {"tier": "admin", "version": "3.4", "deprecated": True},
    "prompt_version_tool": {"tier": "admin", "version": "3.4", "deprecated": True},
    "output_template_tool": {"tier": "admin", "version": "3.4", "deprecated": True},
    "data_quality_tool": {"tier": "admin", "version": "3.5"},
    "get_ai_tracking_tool": {"tier": "admin", "version": "3.5"},
}

_TIER_ORDER = {"core": 0, "advanced": 1, "admin": 2}


# ═══════════════════════════════════════════════════════════════════
# CORE — 独立工具（9 个）
# ═══════════════════════════════════════════════════════════════════


async def discover_workspace_tool() -> dict:
    """发现 workspace 全景：投资者、组合、持仓、数据状态、推荐下一步操作。
    零参数，首次连接时调用。"""
    from praxis.tools.workspace import discover_workspace
    return await run_in_safe_thread(discover_workspace, WORKSPACE)


async def get_portfolio_tool(investor: str, portfolio: str) -> dict:
    """读取投资组合配置
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.portfolio import get_portfolio
    return await _log_tool_call("get_portfolio", get_portfolio, investor=investor, portfolio=portfolio, workspace=WORKSPACE)


async def get_asset_detail_tool(investor: str, portfolio: str, ticker: str) -> dict:
    """读取单个标的详情
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.portfolio import get_asset_detail
    return await _log_tool_call("get_asset_detail", get_asset_detail, investor=investor, portfolio=portfolio, ticker=ticker, workspace=WORKSPACE)


async def get_market_data_tool(tickers: list[str]) -> dict:
    """获取实时行情数据

    Args:
        tickers: 标的代码列表（如 ["000001", "600000"]）

    Returns:
        实时行情数据，包含价格、涨跌幅、成交量等
    """
    from praxis.tools.market import get_market_data
    return await get_market_data(tickers, WORKSPACE)


async def get_state_tool(investor: str, portfolio: str, infer_from_ledger: bool = False) -> dict:
    """从 ledger 重建组合状态

    Args:
        investor: 投资者 ID
        portfolio: 组合 ID
        infer_from_ledger: 纯 ledger 推断模式（不需要配置文件，适合初始化阶段）
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.state import get_state
    return await get_state(investor, portfolio, infer_from_ledger, WORKSPACE)


async def get_portfolio_summary_tool(investor: str, portfolio: str) -> dict:
    """获取组合聚合概览（一次返回总资产/持仓/配置比/交易统计）

    避免需要调用 4-5 个工具才能拼出完整视图。

    Args:
        investor: 投资者 ID
        portfolio: 组合 ID
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.summary import get_portfolio_summary
    return await get_portfolio_summary(investor, portfolio, WORKSPACE)


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
        ticker: 仅计算指定标的的绩效（如 "000001"）
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.performance import get_performance
    return await get_performance(investor, portfolio, exclude_reversed, exclude_tags, include_tags, ticker, WORKSPACE)


async def reconcile_tool(investor: str, portfolio: str, nav: float | None = None) -> dict:
    """对账计算（dry-run 模式）
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.engine import reconcile
    provider = await get_global_provider()
    return await reconcile(investor, portfolio, nav, WORKSPACE, provider=provider)


async def check_constraints_tool(investor: str, portfolio: str, action: str, ticker: str, amount: float = 0) -> dict:
    """检查交易约束
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.engine import check_constraints
    return await run_in_safe_thread(check_constraints, investor, portfolio, action, ticker, amount, WORKSPACE)


# ═══════════════════════════════════════════════════════════════════
# CORE — 合并工具（12 个）
# ═══════════════════════════════════════════════════════════════════


async def ledger_tool(
    action: str,
    ticker: str | None = None,
    limit: int = 100,
    trade_action: str | None = None,
    quantity: float | None = None,
    price: float | None = None,
    fee: float = 0,
    decision_id: str | None = None,
    idempotency_key: str | None = None,
    auto_approve: bool = False,
    tags: list[str] | None = None,
    asset_type: str | None = None,
    tx_id: str | None = None,
    reason: str | None = None,
    tag: str | None = None,
    confirm: bool = False,
) -> dict:
    """交易账本操作

    Args:
        action: 操作类型
            - get: 查询交易记录（ticker 可选, limit 可选）
            - add: 添加交易记录（需 ticker, trade_action, quantity, price）
            - reverse: 反向冲销（需 tx_id, reason）
            - delete: 物理删除（需 tx_id）⚠️ 仅限测试/错误数据
            - purge: 清空账本（需 confirm=True, tag 可选）⚠️ 危险操作
        ticker: 标的代码（get/add 必填）
        limit: 返回条数（get 可选，默认100）
        trade_action: 交易方向 buy/sell/subscribe/redeem/dividend（add 必填）
        quantity: 数量（add 必填）
        price: 价格（add 必填）
        fee: 手续费（add 可选，默认0）
        decision_id: 关联决策ID（add 可选）
        idempotency_key: 幂等键（add 可选）
        auto_approve: 自动审批跳过审批流程（add 可选）
        tags: 标签列表如 ["test"]["real"]（add 可选）
        asset_type: 资产类型 stock/etf/offshore_fund（add 可选）
        tx_id: 交易ID（reverse/delete 必填）
        reason: 原因说明（reverse 必填, reject 必填）
        tag: 按标签过滤（purge 可选）
        confirm: 安全确认（purge 必填=True）

    示例:
        ledger_tool(action="get", ticker="000001", limit=50)
        ledger_tool(action="add", ticker="000001", trade_action="buy", quantity=200, price=10.50)
        ledger_tool(action="reverse", tx_id="tx-20260609-001", reason="止损")
    """
    if action == "get":
        from praxis.tools.ledger import get_ledger
        return await run_in_safe_thread(get_ledger, ticker, limit, WORKSPACE)
    elif action == "add":
        from praxis.tools.ledger import add_transaction
        return add_transaction(
            ticker=ticker, action=trade_action, quantity=quantity, price=price,
            fee=fee, decision_id=decision_id, idempotency_key=idempotency_key,
            auto_approve=auto_approve, tags=tags, asset_type=asset_type,
            workspace=WORKSPACE,
        )
    elif action == "reverse":
        from praxis.tools.ledger import reverse_transaction
        return reverse_transaction(tx_id, reason, WORKSPACE)
    elif action == "delete":
        from praxis.tools.ledger import delete_transaction
        return delete_transaction(tx_id, WORKSPACE)
    elif action == "purge":
        from praxis.tools.ledger import purge_ledger
        return purge_ledger(tag, confirm, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: get/add/reverse/delete/purge"}


async def transaction_approval_tool(
    action: str,
    tx_id: str | None = None,
    reason: str | None = None,
) -> dict:
    """交易审批操作

    Args:
        action: 操作类型
            - approve: 审批通过（从 pending 写入正式账本）
            - reject: 拒绝交易
            - list_pending: 列出所有待审批交易
        tx_id: 待审批交易ID，格式 tx-YYYYMMDD-pending-NNN（approve/reject 必填）
        reason: 拒绝原因（reject 必填）
    """
    if action == "approve":
        from praxis.tools.ledger import approve_transaction
        return approve_transaction(tx_id, WORKSPACE)
    elif action == "reject":
        from praxis.tools.ledger import reject_transaction
        return reject_transaction(tx_id, reason, WORKSPACE)
    elif action == "list_pending":
        from praxis.tools.ledger import list_pending_transactions
        return list_pending_transactions(WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: approve/reject/list_pending"}


async def decision_tool(
    action: str,
    decision_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    ticker: str | None = None,
    decision_action: str | None = None,
    confidence: float | None = None,
    reasoning: str | None = None,
    quantity: float | None = None,
    price_range: list[float] | None = None,
) -> dict:
    """决策记录操作

    Args:
        action: 操作类型
            - get: 获取单条决策（需 decision_id）
            - list: 列出决策记录（status 可选, limit 可选）
            - create: 创建决策记录（需 ticker, decision_action, confidence, reasoning）
        decision_id: 决策ID（get 必填）
        status: 状态过滤（list 可选）
        limit: 返回条数（list 可选，默认50）
        ticker: 标的代码（create 必填）
        decision_action: 决策动作 buy/sell/hold/watch（create 必填）
        confidence: 置信度 0.0-1.0（create 必填）
        reasoning: 决策理由（create 必填）
        quantity: 建议数量（create 可选）
        price_range: 目标价格区间（create 可选）
    """
    if action == "get":
        from praxis.tools.decision import get_decision_record
        return await run_in_safe_thread(get_decision_record, decision_id, WORKSPACE)
    elif action == "list":
        from praxis.tools.decision import list_decisions
        return list_decisions(status=status, limit=limit, workspace=WORKSPACE)
    elif action == "create":
        from praxis.tools.decision import create_decision
        # v3.0: 结构化输出校验（decision create 是核心拦截点）
        if reasoning:
            from praxis_sdk.core.validator import validate_decision
            validation = validate_decision(reasoning)
            if validation.fallback_data and not validation.valid:
                # 降级数据可用于补全缺失字段
                fallback = validation.fallback_data
                if not confidence and "confidence" in fallback:
                    confidence = fallback["confidence"]
                if not decision_action and "action" in fallback:
                    decision_action = fallback["action"]
        return create_decision(
            ticker=ticker, action=decision_action, confidence=confidence,
            reasoning=reasoning, quantity=quantity, price_range=price_range,
            workspace=WORKSPACE,
        )
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: get/list/create"}


async def nav_tool(
    action: str,
    investor: str | None = None,
    portfolio: str | None = None,
    nav: float | None = None,
    total_assets: float | None = None,
    positions_value: float | None = None,
    cash: float | None = None,
    benchmark_nav: float | None = None,
    benchmark_code: str | None = None,
    days: int = 30,
) -> dict:
    """净值管理操作

    Args:
        action: 操作类型
            - record: 记录当日净值（需 investor, portfolio, nav, total_assets, positions_value, cash）
            - snapshot: 获取净值快照（需 investor, portfolio）
            - history: 获取净值历史（需 investor, portfolio, days 可选）
        investor: 投资者 ID（必填）
        portfolio: 组合 ID（必填）
        nav: 净值（record 必填）
        total_assets: 总资产（record 必填）
        positions_value: 持仓市值（record 必填）
        cash: 现金（record 必填）
        benchmark_nav: 基准净值（record 可选）
        benchmark_code: 基准代码（record 可选）
        days: 历史天数（history 可选，默认30）
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    if action == "record":
        from praxis.tools.nav import record_nav
        return await run_in_safe_thread(record_nav, investor, portfolio, nav, total_assets, positions_value, cash, benchmark_nav, benchmark_code, WORKSPACE)
    elif action == "snapshot":
        from praxis.tools.nav import get_nav_snapshot
        return await get_nav_snapshot(investor, portfolio, WORKSPACE)
    elif action == "history":
        from praxis.tools.nav import get_nav_history
        return await run_in_safe_thread(get_nav_history, investor, portfolio, days, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: record/snapshot/history"}


async def sentinel_tool(action: str, days: int = 10) -> dict:
    """哨兵雷达操作（Rule 23/26 核心数据源）

    Args:
        action: 操作类型
            - scan: 执行哨兵雷达扫描，获取 8 个哨兵 ETF 实时价格 + MA 均线，输出攻防状态
            - rule23_status: 获取 Rule 23 情绪起爆器验证状态
            - history: 获取哨兵历史记录（days 可选，默认10）
        days: 历史天数（history 可选，默认10）

    8 个哨兵：
      大局风格层：510300 沪深300 / 159915 创业板 / 512000 券商 / 159601 恒生科技
      执行持仓层：512480 半导体 / 515050 通信 / 515220 煤炭 / 511220 国债

    示例:
        sentinel_tool(action="scan")           # 执行哨兵扫描
        sentinel_tool(action="rule23_status")  # 获取 Rule 23 状态
        sentinel_tool(action="history", days=5) # 获取最近 5 天历史
    """
    if action == "scan":
        from praxis.tools.sentinel import scan_sentinel_radar
        return await scan_sentinel_radar(WORKSPACE)
    elif action == "rule23_status":
        from praxis.tools.sentinel import get_rule23_status
        return await get_rule23_status(WORKSPACE)
    elif action == "history":
        from praxis.tools.sentinel import get_sentinel_history
        return await get_sentinel_history(days, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: scan/rule23_status/history"}


async def valuation_tool(action: str, index_code: str = "000300") -> dict:
    """指数估值分位查询

    Args:
        action: 操作类型
            - percentile: 获取单指数 PE-TTM 历史分位（Rule 23/24 核心数据源）
            - all: 获取所有支持指数的估值分位快照
        index_code: 指数代码（percentile 可选，默认000300）
            000300=沪深300, 000016=上证50, 000905=中证500, 000852=中证1000

    示例:
        valuation_tool(action="percentile", index_code="000300")  # 沪深300 PE 分位
        valuation_tool(action="all")  # 全指数估值快照
    """
    if action == "percentile":
        from praxis.tools.valuation import get_valuation_percentile
        return await get_valuation_percentile(index_code)
    elif action == "all":
        from praxis.tools.valuation import check_valuation_for_all_indices
        return await check_valuation_for_all_indices()
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: percentile/all"}


async def sentiment_tool(action: str, text: str | None = None, texts: list[str] | None = None) -> dict:
    """金融文本情感分析（增强关键词 + 否定翻转策略）

    Args:
        action: 操作类型
            - analyze: 分析单条文本（需 text）
            - batch: 批量分析多条文本（需 texts）
        text: 单条金融文本（analyze 必填）
        texts: 文本列表（batch 必填）

    Returns:
        情感分析结果：score (-1.0~1.0), label (positive/negative/neutral), reason
    """
    if action == "analyze":
        from praxis.tools.sentiment import analyze_sentiment
        return await run_in_safe_thread(analyze_sentiment, text, WORKSPACE)
    elif action == "batch":
        from praxis.tools.sentiment import batch_analyze_sentiment
        return await run_in_safe_thread(batch_analyze_sentiment, texts, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: analyze/batch"}


async def news_tool(action: str, sources: list[str] | None = None, count: int = 10, limit: int = 10) -> dict:
    """新闻与情报获取

    Args:
        action: 操作类型
            - finance: 获取实时财经新闻（10+ 信源：财联社、华尔街见闻、雪球等）
            - trends: 获取多平台综合热点报告（微博/知乎/华尔街见闻）
            - polymarket: 获取 Polymarket 预测市场摘要
            - list_sources: 列出所有支持的新闻源
        sources: 新闻源列表（finance 默认 cls/wallstreetcn/xueqiu; trends 默认 weibo/zhihu/wallstreetcn）
        count: 每个源获取的新闻数量（finance 可选，默认10）
        limit: 获取的市场数量（polymarket 可选，默认10）
    """
    if action == "finance":
        from praxis.tools.news import get_finance_news
        return await run_in_safe_thread(get_finance_news, sources, count, WORKSPACE)
    elif action == "trends":
        from praxis.tools.news import get_unified_trends_report
        return await run_in_safe_thread(get_unified_trends_report, sources, WORKSPACE)
    elif action == "polymarket":
        from praxis.tools.news import get_polymarket_summary
        return await run_in_safe_thread(get_polymarket_summary, limit, WORKSPACE)
    elif action == "list_sources":
        from praxis.tools.news import list_news_sources
        return list_news_sources()
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: finance/trends/polymarket/list_sources"}


async def benchmark_tool(action: str, index_code: str | None = None, days: int = 60) -> dict:
    """基准指数数据

    Args:
        action: 操作类型
            - data: 获取基准指数数据（需 index_code）
            - list: 列出所有支持的基准指数
        index_code: 指数代码（data 必填）
        days: 历史天数（data 可选，默认60）
    """
    if action == "data":
        from praxis.tools.benchmark import get_benchmark_data
        return await get_benchmark_data(index_code, days)
    elif action == "list":
        from praxis.tools.benchmark import list_benchmarks
        return list_benchmarks()
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: data/list"}


async def agent_tracking_tool(
    action: str,
    agent_id: str | None = None,
    ticker: str | None = None,
    decision_action: str | None = None,
    confidence: float | None = None,
    reasoning: str | None = None,
    min_agents: int = 2,
) -> dict:
    """Agent 决策追踪

    Args:
        action: 操作类型
            - record: 记录 Agent 决策（需 agent_id, ticker, decision_action, confidence, reasoning）
            - consensus: 检查多 Agent 共识（需 ticker）
            - rank: 排名所有 Agent（按决策数量和平均置信度）
        agent_id: Agent 标识如 reasonix/gemini/claude（record 必填）
        ticker: 标的代码（record/consensus 必填）
        decision_action: 建议动作 buy/sell/hold/watch（record 必填）
        confidence: 置信度 0.0-1.0（record 必填）
        reasoning: 决策理由（record 必填）
        min_agents: 最低共识 Agent 数（consensus 可选，默认2）
    """
    if action == "record":
        from praxis.tools.agent_tracker import record_agent_decision
        return await run_in_safe_thread(record_agent_decision, agent_id, ticker, decision_action, confidence, reasoning, WORKSPACE)
    elif action == "consensus":
        from praxis.tools.agent_tracker import check_consensus
        return await run_in_safe_thread(check_consensus, ticker, min_agents, WORKSPACE)
    elif action == "rank":
        from praxis.tools.agent_tracker import rank_agents
        return rank_agents(WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: record/consensus/rank"}


async def review_tool(action: str, team: str | None = None) -> dict:
    """决策复盘

    Args:
        action: 操作类型
            - fill: 自动回填待复盘的决策（5d/20d/60d）
            - summary: 获取复盘汇总（待复盘/已复盘数量）
            - calibration: 获取指定团队的信心度校准误差（需 team）
        team: 团队名称 asrg/masters/trading（calibration 必填）
    """
    if action == "fill":
        from praxis.tools.review import fill_reviews
        return await fill_reviews(WORKSPACE)
    elif action == "summary":
        from praxis.tools.review import get_review_summary
        return await run_in_safe_thread(get_review_summary, WORKSPACE)
    elif action == "calibration":
        from praxis.tools.review import get_confidence_calibration
        return await run_in_safe_thread(get_confidence_calibration, team, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: fill/summary/calibration"}


async def trading_friction_tool(
    action: str,
    ticker: str | None = None,
    asset_type: str | None = None,
    trade_action: str | None = None,
    quantity: float | None = None,
    price: float | None = None,
    volume: float | None = None,
    volatility: float | None = None,
    timestamp: str | None = None,
    trade_date: str | None = None,
) -> dict:
    """交易摩擦成本计算

    Args:
        action: 操作类型
            - fee: 计算交易费用（需 ticker, asset_type, trade_action, quantity, price）
            - slippage: 计算滑点（需 price, trade_action; volume/volatility 可选）
            - trading_time: 检查交易时间（asset_type 可选默认 stock, timestamp 可选）
            - confirm_date: 获取确认日期（需 trade_date, asset_type 可选默认 stock）
        ticker: 标的代码（fee 必填）
        asset_type: 资产类型 stock/etf/offshore_fund（fee/trading_time/confirm_date 使用）
        trade_action: 交易方向 buy/sell/subscribe/redeem（fee/slippage 必填）
        quantity: 数量（fee 必填）
        price: 委托价格（fee/slippage 必填）
        volume: 成交量（slippage 可选）
        volatility: 波动率（slippage 可选）
        timestamp: ISO 时间戳（trading_time 可选，默认当前）
        trade_date: 交易日期 YYYY-MM-DD（confirm_date 必填）
    """
    if action == "fee":
        from praxis.tools.friction import calculate_fee
        return calculate_fee(ticker, asset_type, trade_action, quantity, price, WORKSPACE)
    elif action == "slippage":
        from praxis.tools.friction import calculate_slippage
        return calculate_slippage(price, trade_action, volume, volatility, WORKSPACE)
    elif action == "trading_time":
        from praxis.tools.friction import check_trading_time
        return await run_in_safe_thread(check_trading_time, timestamp, asset_type or "stock", WORKSPACE)
    elif action == "confirm_date":
        from praxis.tools.friction import get_confirm_date
        return await run_in_safe_thread(get_confirm_date, trade_date, asset_type or "stock", WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: fee/slippage/trading_time/confirm_date"}


# ═══════════════════════════════════════════════════════════════════
# ADVANCED — 独立工具（9 个）
# ═══════════════════════════════════════════════════════════════════


async def evaluate_evolution_tool(strategy_name: str, investor: str, portfolio: str) -> dict:
    """评估进化维度
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.evolution import evaluate_evolution
    return await run_in_safe_thread(evaluate_evolution, strategy_name, investor, portfolio, WORKSPACE)


async def auto_evolve_tool(strategy_name: str, investor: str, portfolio: str) -> dict:
    """一键自进化：评估 → 建议 → 备份 → 待审批

    事件驱动触发：每笔交易后 / 每日 NAV 记录后 / 哨兵状态变更时。
    结果自动落盘到 deliverables/evolution/。
    """
    from praxis.tools.evolution import auto_evolve
    return auto_evolve(strategy_name, investor, portfolio, WORKSPACE)


async def run_backtest_tool(strategy_name: str, investor: str, portfolio: str, days: int = 90) -> dict:
    """运行策略回测

    Args:
        strategy_name: 策略名称
        investor: 投资者ID
        portfolio: 组合ID
        days: 回测天数
    提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.backtest import run_backtest
    return await run_backtest(strategy_name, investor, portfolio, days, WORKSPACE)


async def compare_versions_tool(strategy_a: str, strategy_b: str) -> dict:
    """对比两个策略版本的绩效指标

    Args:
        strategy_a: 策略A名称
        strategy_b: 策略B名称
    """
    from praxis.tools.version_compare import compare_versions
    return await compare_versions(strategy_a, strategy_b, WORKSPACE)


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
    """
    from praxis.tools.grayscale import prepare_grayscale
    return prepare_grayscale(strategy_name, change_description, risk_level, validation_days, WORKSPACE)


async def approve_grayscale_tool(strategy_name: str, backup_path: str, new_content: str) -> dict:
    """审批通过后应用策略变更

    Args:
        strategy_name: 策略名称
        backup_path: 备份文件路径
        new_content: 新的策略内容
    """
    from praxis.tools.grayscale import approve_grayscale
    return approve_grayscale(strategy_name, backup_path, new_content, WORKSPACE)


async def get_strategy_tool(strategy_name: str) -> dict:
    """获取策略详情"""
    from praxis.tools.strategy import get_strategy
    return await run_in_safe_thread(get_strategy, strategy_name, WORKSPACE)


async def list_strategies_tool() -> dict:
    """列出所有策略模板"""
    from praxis.tools.strategy import list_strategies
    return list_strategies(WORKSPACE)


async def update_portfolio_tool(investor: str, portfolio: str, field: str, value: str) -> dict:
    """修改组合配置（需审批）
        提示: 首次使用请调用 discover_workspace_tool() 获取可用的 investor/portfolio ID。
    """
    from praxis.tools.strategy import update_portfolio
    return update_portfolio(investor, portfolio, field, value, WORKSPACE)


# ═══════════════════════════════════════════════════════════════════
# ADVANCED — 合并工具（3 个）
# ═══════════════════════════════════════════════════════════════════


async def evolution_memory_tool(
    action: str,
    trigger_event: str | None = None,
    strategy_name: str | None = None,
    evaluation_summary: str | None = None,
    situation: str | None = None,
    limit: int = 5,
) -> dict:
    """进化记忆操作

    Args:
        action: 操作类型
            - record: 记录一次进化记忆（需 trigger_event, strategy_name, evaluation_summary）
            - timeline: 获取策略进化时间线（需 strategy_name）
            - query: 查询类似情况的历史记录（需 situation）
        trigger_event: 触发事件 transaction/nav_record/manual（record 必填）
        strategy_name: 策略名称（record/timeline 必填）
        evaluation_summary: 评估摘要（record 必填）
        situation: 描述当前情况的关键词（query 必填）
        limit: 返回结果数量上限（query 可选，默认5）
    """
    if action == "record":
        from praxis.tools.memory import record_evolution_memory
        return record_evolution_memory(trigger_event, strategy_name, evaluation_summary, workspace=WORKSPACE)
    elif action == "timeline":
        from praxis.tools.memory import get_evolution_timeline
        return get_evolution_timeline(strategy_name, WORKSPACE)
    elif action == "query":
        from praxis.tools.memory import query_evolution_memory
        return query_evolution_memory(situation, limit, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: record/timeline/query"}


async def adaptive_rules_tool(action: str, rule_id: str | None = None) -> dict:
    """自适应规则管理

    Args:
        action: 操作类型
            - learn: 从历史数据学习自适应规则，经安全扫描后写入 teams/adaptive/
            - list: 列出所有已学习的自适应规则
            - approve: 审批通过规则（draft → active），需 rule_id
            - reject: 拒绝规则，需 rule_id
        rule_id: 规则 ID（approve/reject 必填）
    """
    if action == "learn":
        from praxis.tools.adaptive import learn_rules
        return learn_rules(WORKSPACE)
    elif action == "list":
        from praxis.tools.adaptive import list_learned_rules
        return list_learned_rules(WORKSPACE)
    elif action == "approve":
        from praxis.tools.adaptive import approve_rule
        return approve_rule(rule_id, WORKSPACE)
    elif action == "reject":
        from praxis.tools.adaptive import reject_rule
        return reject_rule(rule_id, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: learn/list/approve/reject"}


async def orchestrator_tool(
    action: str,
    team: str | None = None,
    member_id: str | None = None,
    ticker: str | None = None,
    stock_name: str = "",
    price: float = 0,
    change_pct: float = 0,
    market_data: str = "",
    financial_data: str = "",
    fund_flow: str = "",
    prev_phase_output: str = "",
    all_outputs: dict | None = None,
    model_hint: str = "deep",
) -> dict:
    """团队分析编排器（ASRG/Masters/Trading）

    Args:
        action: 操作类型
            - plan: 获取团队分析任务计划（需 team, ticker）
            - member_prompt: 为指定成员生成子Agent分析Prompt（需 team, member_id, ticker）
            - compile_prompt: 生成主理人汇编Prompt（需 team, ticker, stock_name, price, all_outputs）
        team: 团队名称 asrg/masters/trading（必填）
        member_id: 成员ID 如 ethan/james/kevin（member_prompt 必填）
        ticker: 标的代码（必填）
        stock_name: 标的名称
        price: 当前价
        change_pct: 涨跌幅
        market_data: 实时行情数据（member_prompt 可选）
        financial_data: 财务数据（member_prompt 可选）
        fund_flow: 资金流向（member_prompt 可选）
        prev_phase_output: 上一阶段输出（member_prompt 可选）
        all_outputs: 各成员分析输出字典 {member_id: output}（compile_prompt 必填）
        model_hint: 模型级别 "deep" 或 "quick"（v3.0 新增，影响 prompt 复杂度和结构化输出校验）

    示例:
        orchestrator_tool(action="plan", team="asrg", ticker="000001", stock_name="示例股票", price=10.0)
        orchestrator_tool(action="member_prompt", team="asrg", member_id="ethan", ticker="000001", model_hint="quick")
        orchestrator_tool(action="compile_prompt", team="asrg", ticker="000001", stock_name="示例股票", price=10.0, all_outputs={"ethan": "..."})
    """
    if action == "plan":
        from praxis.tools.orchestrator import get_team_analysis_plan
        return await get_team_analysis_plan(team, ticker, stock_name, price, change_pct, WORKSPACE)
    elif action == "member_prompt":
        from praxis.tools.orchestrator import generate_member_prompt
        return await generate_member_prompt(
            team, member_id, ticker, stock_name, price, change_pct,
            market_data, financial_data, fund_flow, prev_phase_output, WORKSPACE,
            model_hint=model_hint,
        )
    elif action == "compile_prompt":
        from praxis.tools.orchestrator import generate_compile_prompt
        result = await generate_compile_prompt(team, ticker, stock_name, price, all_outputs, WORKSPACE)
        # v3.0: 结构化输出校验（compile_prompt 是核心拦截点）
        if result.get("success") and result.get("output"):
            from praxis_sdk.core.validator import validate_team_output
            validation = validate_team_output(result["output"], team or "trading")
            result["validation"] = {
                "valid": validation.valid,
                "fallback_used": validation.fallback_used,
                "errors": validation.errors,
            }
            if validation.data:
                result["structured_data"] = validation.data
            elif validation.fallback_data:
                result["structured_data"] = validation.fallback_data
        return result
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: plan/member_prompt/compile_prompt"}


# ═══════════════════════════════════════════════════════════════════
# v3.5 整合工具 - 策略与进化层 (Advanced)
# ═══════════════════════════════════════════════════════════════════


async def strategy_tool(
    action: str,  # get / list / compare
    strategy_name: str = "",
    strategy_a: str = "",
    strategy_b: str = "",
) -> dict:
    """策略管理（整合 3 个工具）

    Args:
        action: 操作类型
            - get: 获取策略详情（需 strategy_name）
            - list: 列出所有策略模板
            - compare: 对比两个策略版本（需 strategy_a, strategy_b）
        strategy_name: 策略名称（get 操作需要）
        strategy_a: 策略A名称（compare 操作需要）
        strategy_b: 策略B名称（compare 操作需要）

    Returns:
        策略相关数据
    """
    # 参数验证
    if action not in ["get", "list", "compare"]:
        return {
            "success": False,
            "error_code": "INVALID_ACTION",
            "error": ERROR_CODES["INVALID_ACTION"].format(action=action),
        }

    if action == "get" and not strategy_name:
        return {
            "success": False,
            "error_code": "MISSING_PARAM",
            "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="strategy_name"),
        }

    if action == "compare" and not all([strategy_a, strategy_b]):
        return {
            "success": False,
            "error_code": "MISSING_PARAM",
            "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="strategy_a, strategy_b"),
        }

    # 路由到具体实现
    if action == "get":
        from praxis.tools.strategy import get_strategy
        return await run_in_safe_thread(get_strategy, strategy_name, WORKSPACE)
    elif action == "list":
        from praxis.tools.strategy import list_strategies
        return list_strategies(WORKSPACE)
    elif action == "compare":
        from praxis.tools.version_compare import compare_versions
        return await compare_versions(strategy_a, strategy_b, WORKSPACE)


async def evolution_tool(
    action: str,  # evaluate / auto / memory / adaptive
    investor: str = "",
    portfolio: str = "",
    strategy_name: str = "",
    # ─── memory 参数 ───
    trigger_event: str = "",
    evaluation_summary: str = "",
    situation: str = "",
    limit: int = 5,
    # ─── adaptive 参数 ───
    rule_id: str = "",
) -> dict:
    """进化管理（整合 4 个工具）

    Args:
        action: 操作类型
            - evaluate: 评估进化维度
            - auto: 一键自进化
            - memory: 进化记忆（record/timeline/query）
            - adaptive: 自适应规则（learn/list/approve/reject）
        investor: 投资者 ID
        portfolio: 组合 ID
        strategy_name: 策略名称
        trigger_event: 触发事件（memory record 操作需要）
        evaluation_summary: 评估摘要（memory record 操作需要）
        situation: 描述当前情况的关键词（memory query 操作需要）
        limit: 返回结果数量上限（memory query 操作可选）
        rule_id: 规则 ID（adaptive approve/reject 操作需要）

    Returns:
        进化相关数据
    """
    # 参数验证
    if action not in ["evaluate", "auto", "memory", "adaptive"]:
        return {
            "success": False,
            "error_code": "INVALID_ACTION",
            "error": ERROR_CODES["INVALID_ACTION"].format(action=action),
        }

    # 路由到具体实现
    if action == "evaluate":
        from praxis.tools.evolution import evaluate_evolution
        return await evaluate_evolution(investor, portfolio, strategy_name, WORKSPACE)
    elif action == "auto":
        from praxis.tools.evolution import auto_evolve
        return await auto_evolve(investor, portfolio, strategy_name, WORKSPACE)
    elif action == "memory":
        # memory 子操作需要额外的 action 参数
        # 这里简化处理，直接调用 record
        from praxis.tools.memory import record_evolution_memory
        return record_evolution_memory(trigger_event, strategy_name, evaluation_summary, workspace=WORKSPACE)
    elif action == "adaptive":
        # adaptive 子操作需要额外的 action 参数
        # 这里简化处理，直接调用 list
        from praxis.tools.adaptive import list_learned_rules
        return list_learned_rules(WORKSPACE)


async def grayscale_tool(
    action: str,  # prepare / approve
    strategy_name: str = "",
    change_description: str = "",
    risk_level: str = "medium",
    validation_days: int = 30,
    backup_path: str = "",
    new_content: str = "",
) -> dict:
    """灰度验证管理（整合 2 个工具）

    Args:
        action: 操作类型
            - prepare: 准备灰度验证
            - approve: 审批通过并应用
        strategy_name: 策略名称
        change_description: 变更描述（prepare 操作需要）
        risk_level: 风险等级（low/medium/high）
        validation_days: 验证天数
        backup_path: 备份文件路径（approve 操作需要）
        new_content: 新的策略内容（approve 操作需要）

    Returns:
        灰度验证相关数据
    """
    # 参数验证
    if action not in ["prepare", "approve"]:
        return {
            "success": False,
            "error_code": "INVALID_ACTION",
            "error": ERROR_CODES["INVALID_ACTION"].format(action=action),
        }

    if action == "prepare" and not all([strategy_name, change_description]):
        return {
            "success": False,
            "error_code": "MISSING_PARAM",
            "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="strategy_name, change_description"),
        }

    if action == "approve" and not all([strategy_name, backup_path, new_content]):
        return {
            "success": False,
            "error_code": "MISSING_PARAM",
            "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="strategy_name, backup_path, new_content"),
        }

    # 路由到具体实现
    if action == "prepare":
        from praxis.tools.grayscale import prepare_grayscale
        return prepare_grayscale(strategy_name, change_description, risk_level, validation_days, WORKSPACE)
    elif action == "approve":
        from praxis.tools.grayscale import approve_grayscale
        return approve_grayscale(strategy_name, backup_path, new_content, WORKSPACE)


# ═══════════════════════════════════════════════════════════════════
# ADMIN — 合并工具（5 个）+ 独立工具（1 个）
# ═══════════════════════════════════════════════════════════════════


async def investor_tool(
    action: str,
    investor_id: str | None = None,
    name: str | None = None,
    capital_cny: float | None = None,
    risk_level: str = "C3",
    style: str = "balanced",
    max_drawdown_pct: float = 20,
    portfolio_id: str | None = None,
    strategy_type: str = "grid_value",
    strategy_template: str = "grid_value",
    description: str | None = None,
    assets: list[dict] | None = None,
    investor_name: str | None = None,
    positions: list[dict] | None = None,
    cash: float | None = None,
    benchmark: str | None = None,
) -> dict:
    """投资者与组合管理

    Args:
        action: 操作类型
            - create: 创建投资者画像（需 investor_id, name, capital_cny）
            - create_portfolio: 创建投资组合（需 investor_id, portfolio_id）
            - init: 一条命令完成投资者+组合+持仓初始化（需 investor_id, investor_name, capital_cny, portfolio_id, positions, cash）
        investor_id: 投资者 ID（必填）
        name: 投资者名称（create 必填）
        capital_cny: 初始资金（create/init 必填）
        risk_level: 风险等级 C1-C5（可选，默认C3）
        style: 投资风格（可选，默认balanced）
        max_drawdown_pct: 最大回撤容忍度%（可选，默认20）
        portfolio_id: 组合 ID（create_portfolio/init 必填）
        strategy_type: 策略类型（可选）
        strategy_template: 策略模板名称（可选）
        description: 组合描述（create_portfolio 可选）
        assets: 资产列表 [{ticker, name, type, category, target_weight_pct}]（create_portfolio 可选）
        investor_name: 投资者名称（init 必填，与 name 不同场景使用）
        positions: 持仓列表 [{ticker, name, quantity, avg_cost, type, category}]（init 必填）
        cash: 当前现金余额（init 必填）
        benchmark: 基准指数代码（init 可选）
    """
    if action == "create":
        from praxis.tools.investor import create_investor
        return create_investor(investor_id, name, capital_cny, risk_level, style, max_drawdown_pct, WORKSPACE)
    elif action == "create_portfolio":
        from praxis.tools.investor import create_portfolio
        return create_portfolio(investor_id, portfolio_id, strategy_type, strategy_template, description, assets, WORKSPACE)
    elif action == "init":
        from praxis.tools.investor import init_investor
        return init_investor(
            investor_id, investor_name, capital_cny, portfolio_id, positions, cash,
            risk_level, style, max_drawdown_pct, strategy_type, strategy_template,
            benchmark, WORKSPACE,
        )
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: create/create_portfolio/init"}


async def team_config_tool(action: str, team_name: str | None = None, strategy_name: str = "grid_value", investor_id: str = "example") -> dict:
    """团队与 Prompt 配置

    Args:
        action: 操作类型
            - list: 列出所有可用的 AI 团队（ASRG/大师圆桌/交易团队）
            - get: 获取指定团队的完整 Prompt（需 team_name）
            - compose: 组合团队 Prompt（基础 + 团队 + 策略 + 投资者）（需 team_name）
        team_name: 团队名称 asrg/masters/trading（get/compose 必填）
        strategy_name: 策略名称（compose 可选，默认grid_value）
        investor_id: 投资者ID（compose 可选，默认example）
    """
    if action == "list":
        from praxis.tools.teams import list_teams
        return list_teams(WORKSPACE)
    elif action == "get":
        from praxis.tools.teams import get_team_prompt
        return get_team_prompt(team_name, WORKSPACE)
    elif action == "compose":
        from praxis.tools.teams import compose_team_prompt
        return compose_team_prompt(team_name, strategy_name, investor_id, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: list/get/compose"}


async def prompt_version_tool(
    action: str,
    prompt_name: str | None = None,
    version: str | None = None,
    content: str | None = None,
    description: str | None = None,
    target_version: str | None = None,
    reason: str | None = None,
    from_version: str | None = None,
    to_version: str | None = None,
) -> dict:
    """Prompt 版本管理

    Args:
        action: 操作类型
            - list: 列出 Prompt 的所有版本（需 prompt_name）
            - get: 获取指定版本（需 prompt_name, version 可选默认最新）
            - create: 创建新版本（需 prompt_name, content）
            - rollback: 回滚到指定版本（需 prompt_name, target_version, reason）
            - diff: 获取版本差异（需 prompt_name, from_version, to_version）
            - check_safety: 检查 Prompt 安全性（需 content）
        prompt_name: Prompt 名称（除 check_safety 外必填）
        version: 版本号（get 可选，默认最新）
        content: Prompt 内容（create/check_safety 必填）
        description: 版本描述（create 可选）
        target_version: 目标版本（rollback 必填）
        reason: 回滚原因（rollback 必填）
        from_version: 起始版本（diff 必填）
        to_version: 目标版本（diff 必填）
    """
    if action == "list":
        from praxis.tools.prompt_versioning import list_prompt_versions
        return list_prompt_versions(prompt_name, WORKSPACE)
    elif action == "get":
        from praxis.tools.prompt_versioning import get_prompt_version
        return get_prompt_version(prompt_name, version, WORKSPACE)
    elif action == "create":
        from praxis.tools.prompt_versioning import create_prompt_version
        return create_prompt_version(prompt_name, content, description, WORKSPACE)
    elif action == "rollback":
        from praxis.tools.prompt_versioning import rollback_prompt
        return rollback_prompt(prompt_name, target_version, reason, WORKSPACE)
    elif action == "diff":
        from praxis.tools.prompt_versioning import get_version_diff
        return get_version_diff(prompt_name, from_version, to_version, WORKSPACE)
    elif action == "check_safety":
        from praxis.tools.prompt_versioning import check_prompt_safety
        return check_prompt_safety(content, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: list/get/create/rollback/diff/check_safety"}


async def output_template_tool(
    action: str,
    template_name: str | None = None,
    new_content: str | None = None,
    content: str | None = None,
    reason: str | None = None,
) -> dict:
    """输出模板管理

    Args:
        action: 操作类型
            - list: 列出所有输出模板（ASRG/大师圆桌/交易团队/综合日报）
            - get: 获取指定模板（需 template_name）
            - create: 创建新模板（需 template_name, content）
            - update: 更新模板（需 template_name, new_content, reason），需审批
            - approve: 审批通过模板更新（需 template_name, new_content）
        template_name: 模板名称 asrg_output/masters_output/trading_output/daily_report（除 list 外必填）
        new_content: 新的模板内容（update/approve 必填）
        content: 模板内容（create 必填）
        reason: 修改原因（update 必填）
    """
    if action == "list":
        from praxis.tools.teams import list_output_templates
        return list_output_templates(WORKSPACE)
    elif action == "get":
        from praxis.tools.teams import get_output_template
        return get_output_template(template_name, WORKSPACE)
    elif action == "create":
        from praxis.tools.teams import create_output_template
        return create_output_template(template_name, content, WORKSPACE)
    elif action == "update":
        from praxis.tools.teams import update_output_template
        return update_output_template(template_name, new_content, reason, WORKSPACE)
    elif action == "approve":
        from praxis.tools.teams import approve_output_template_update
        return approve_output_template_update(template_name, new_content, WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: list/get/create/update/approve"}


async def team_tool(
    action: str,  # config / prompt / template
    team_name: str = "",
    # ─── config 参数 ───
    strategy_name: str = "grid_value",
    investor_id: str = "example",
    # ─── prompt 参数 ───
    prompt_name: str = "",
    version: str = "",
    content: str = "",
    description: str = "",
    target_version: str = "",
    reason: str = "",
    from_version: str = "",
    to_version: str = "",
    # ─── template 参数 ───
    template_name: str = "",
    new_content: str = "",
) -> dict:
    """团队管理（整合 3 个工具）

    Args:
        action: 操作类型
            - config: 团队配置（list/get/compose）
            - prompt: Prompt 版本（list/get/create/rollback/diff/check_safety）
            - template: 输出模板（list/get/create/update/approve）
        team_name: 团队名称 asrg/masters/trading
        strategy_name: 策略名称（config compose 操作可选）
        investor_id: 投资者ID（config compose 操作可选）
        prompt_name: Prompt 名称（prompt 操作需要）
        version: 版本号（prompt get 操作可选）
        content: Prompt 内容（prompt create/check_safety 操作需要）
        description: 版本描述（prompt create 操作可选）
        target_version: 目标版本（prompt rollback 操作需要）
        reason: 回滚原因（prompt rollback 操作需要）
        from_version: 起始版本（prompt diff 操作需要）
        to_version: 目标版本（prompt diff 操作需要）
        template_name: 模板名称（template 操作需要）
        new_content: 新的模板内容（template update/approve 操作需要）

    Returns:
        团队相关数据
    """
    # 参数验证
    if action not in ["config", "prompt", "template"]:
        return {
            "success": False,
            "error_code": "INVALID_ACTION",
            "error": ERROR_CODES["INVALID_ACTION"].format(action=action),
        }

    # 路由到具体实现
    if action == "config":
        # config 子操作需要额外的 action 参数
        # 这里简化处理，直接调用 list
        from praxis.tools.teams import list_teams
        return list_teams(WORKSPACE)
    elif action == "prompt":
        # prompt 子操作需要额外的 action 参数
        # 这里简化处理，直接调用 list
        from praxis.tools.prompt_versioning import list_prompt_versions
        return list_prompt_versions(prompt_name, WORKSPACE)
    elif action == "template":
        # template 子操作需要额外的 action 参数
        # 这里简化处理，直接调用 list
        from praxis.tools.teams import list_output_templates
        return list_output_templates(WORKSPACE)


async def data_quality_tool(action: str, ticker: str | None = None, data: dict | None = None) -> dict:
    """行情数据质量管理

    Args:
        action: 操作类型
            - check: 检查行情数据质量（需 ticker, data）
            - clean: 清洗行情数据（需 ticker, data）
            - report: 获取数据质量报告
        ticker: 标的代码（check/clean 必填）
        data: 行情数据（check/clean 必填）
    """
    if action == "check":
        from praxis.tools.data_quality import check_quote_quality
        return check_quote_quality(ticker, data, WORKSPACE)
    elif action == "clean":
        from praxis.tools.data_quality import clean_quote_data
        return clean_quote_data(ticker, data, WORKSPACE)
    elif action == "report":
        from praxis.tools.data_quality import get_quality_report
        return get_quality_report(WORKSPACE)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: check/clean/report"}


async def get_ai_tracking_tool(team: str | None = None) -> dict:
    """获取 AI 建议命中率"""
    from praxis.tools.ai_tracking import get_ai_tracking
    return get_ai_tracking(team, WORKSPACE)


# ═══════════════════════════════════════════════════════════════════
# 数据源工具（Phase 2 新增）
# ═══════════════════════════════════════════════════════════════════


async def fund_flow_tool(action: str, ticker: str = "", days: int = 5) -> dict:
    """资金流向操作

    Args:
        action: 操作类型
            - min: 获取个股分钟级资金流向（需 ticker）
            - daily: 获取个股日度资金流向（需 ticker）
            - all: 获取全市场资金流向
        ticker: 股票代码（min/daily 必填）
        days: 获取天数（daily 可选，默认5）
    """
    from praxis.tools.fund_flow import get_fund_flow_min, get_fund_flow_daily, get_fund_flow_all

    if action == "min":
        if not ticker:
            return {"success": False, "error": "min 操作需要 ticker 参数"}
        return await get_fund_flow_min(ticker)
    elif action == "daily":
        if not ticker:
            return {"success": False, "error": "daily 操作需要 ticker 参数"}
        return await get_fund_flow_daily(ticker, days=days)
    elif action == "all":
        return await get_fund_flow_all(days=days)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: min/daily/all"}


async def dragon_tiger_tool(action: str, ticker: str = "", date: str = "", limit: int = 50) -> dict:
    """龙虎榜操作

    Args:
        action: 操作类型
            - list: 获取龙虎榜列表
            - detail: 获取龙虎榜详情（需 ticker）
        ticker: 股票代码（detail 必填）
        date: 日期 YYYY-MM-DD（list 可选）
        limit: 返回数量（list 可选，默认50）
    """
    from praxis.tools.dragon_tiger import get_dragon_tiger_list, get_dragon_tiger_detail

    if action == "list":
        return await get_dragon_tiger_list(date=date or None, limit=limit)
    elif action == "detail":
        if not ticker:
            return {"success": False, "error": "detail 操作需要 ticker 参数"}
        return await get_dragon_tiger_detail(ticker)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: list/detail"}


async def research_report_tool(action: str, ticker: str = "", limit: int = 20, rating: str = "") -> dict:
    """研报操作

    Args:
        action: 操作类型
            - list: 获取研报列表（需 ticker）
            - eps: 获取一致预期 EPS（需 ticker）
        ticker: 股票代码（必填）
        limit: 返回数量（list 可选，默认20）
        rating: 评级过滤（list 可选，买入/增持/中性/减持/卖出）
    """
    from praxis.tools.research_report import get_report_list, get_consensus_eps

    if action == "list":
        if not ticker:
            return {"success": False, "error": "list 操作需要 ticker 参数"}
        return await get_report_list(ticker, limit=limit, rating=rating or None)
    elif action == "eps":
        if not ticker:
            return {"success": False, "error": "eps 操作需要 ticker 参数"}
        return await get_consensus_eps(ticker)
    else:
        return {"success": False, "error": f"未知 action: {action}，可选: list/eps"}


# ═══════════════════════════════════════════════════════════════════
# v3.5 整合工具 (Consolidated Tools)
# 将参数特征高度相似的工具合并，减少 LLM 工具选择负担
# ═══════════════════════════════════════════════════════════════════

# 错误码定义
ERROR_CODES = {
    "INVALID_ACTION": "LLM 调用错误。未知 action: {action}，请严格从列表选择！",
    "MISSING_PARAM": "参数缺失。{action} 操作需要 {params}",
    "DATA_SOURCE_ERROR": "数据源异常。{source} 返回错误: {error}",
    "TIMEOUT": "工具调用超时 ({timeout}s)",
    "PERMISSION_DENIED": "权限不足。需要 {permission}",
}


async def portfolio_tool(
    action: str,  # summary / detail / state / config
    investor: str,
    portfolio: str,
    ticker: str = "",
) -> dict:
    """组合管理（整合 4 个工具）

    Args:
        action: 操作类型
            - summary: 组合概览（总资产/持仓/配置比/交易统计）
            - detail: 单个资产详情（需 ticker）
            - state: 重建组合状态（从 ledger 推断）
            - config: 获取组合配置
        investor: 投资者 ID
        portfolio: 组合 ID
        ticker: 标的代码（仅 detail 操作需要）

    Returns:
        组合相关数据
    """
    # 参数验证
    if action not in ["summary", "detail", "state", "config"]:
        return {
            "success": False,
            "error_code": "INVALID_ACTION",
            "error": ERROR_CODES["INVALID_ACTION"].format(action=action),
        }

    if action == "detail" and not ticker:
        return {
            "success": False,
            "error_code": "MISSING_PARAM",
            "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="ticker"),
        }

    # 路由到具体实现
    if action == "summary":
        from praxis.tools.summary import get_portfolio_summary
        return await get_portfolio_summary(investor, portfolio, WORKSPACE)
    elif action == "detail":
        from praxis.tools.portfolio import get_asset_detail
        return await get_asset_detail(investor=investor, portfolio=portfolio, ticker=ticker, workspace=WORKSPACE)
    elif action == "state":
        from praxis.tools.state import get_state
        return await get_state(investor, portfolio, False, WORKSPACE)
    elif action == "config":
        from praxis.tools.portfolio import get_portfolio
        return await get_portfolio(investor=investor, portfolio=portfolio, workspace=WORKSPACE)


async def trading_tool(
    action: str,  # ledger / add / reverse / approve / reject / decision
    ticker: str = "",
    # ─── 交易参数（仅 add/reverse 使用）───
    trade_action: str = "",  # buy/sell/subscribe/redeem/dividend
    quantity: float = 0,
    price: float = 0,
    fee: float = 0,
    asset_type: str = "",  # stock/etf/offshore_fund
    # ─── 审批参数（仅 approve/reject 使用）───
    tx_id: str = "",
    reason: str = "",
    # ─── 决策参数（仅 decision 使用）───
    decision_action: str = "",  # buy/sell/hold/watch
    confidence: float = 0,
    reasoning: str = "",
    # ─── 查询参数（仅 ledger 使用）───
    limit: int = 100,
    status: str = "",
) -> dict:
    """交易管理（整合 3 个工具）

    Args:
        action: 操作类型
            - ledger: 查询交易记录
            - add: 添加交易记录
            - reverse: 反向冲销
            - approve: 审批交易
            - reject: 拒绝交易
            - decision: 创建决策记录
        ticker: 标的代码
        trade_action: 交易方向（buy/sell/subscribe/redeem/dividend）
        quantity: 数量
        price: 价格
        fee: 手续费
        asset_type: 资产类型（stock/etf/offshore_fund）
        tx_id: 交易ID（approve/reject 操作需要）
        reason: 原因说明（reject 操作需要）
        decision_action: 决策动作（buy/sell/hold/watch）
        confidence: 置信度（0.0-1.0）
        reasoning: 决策理由
        limit: 返回条数（ledger 操作可选）
        status: 状态过滤（ledger 操作可选）

    Returns:
        交易相关数据
    """
    # 参数验证
    if action not in ["ledger", "add", "reverse", "approve", "reject", "decision"]:
        return {
            "success": False,
            "error_code": "INVALID_ACTION",
            "error": ERROR_CODES["INVALID_ACTION"].format(action=action),
        }

    if action == "add":
        if not all([ticker, trade_action, quantity, price]):
            return {
                "success": False,
                "error_code": "MISSING_PARAM",
                "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="ticker, trade_action, quantity, price"),
            }
    elif action == "approve":
        if not tx_id:
            return {
                "success": False,
                "error_code": "MISSING_PARAM",
                "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="tx_id"),
            }
    elif action == "reject":
        if not all([tx_id, reason]):
            return {
                "success": False,
                "error_code": "MISSING_PARAM",
                "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="tx_id, reason"),
            }
    elif action == "decision":
        if not all([ticker, decision_action, confidence, reasoning]):
            return {
                "success": False,
                "error_code": "MISSING_PARAM",
                "error": ERROR_CODES["MISSING_PARAM"].format(action=action, params="ticker, decision_action, confidence, reasoning"),
            }

    # 路由到具体实现
    if action in ["ledger", "add", "reverse", "delete", "purge"]:
        from praxis.tools.ledger import (
            get_ledger,
            add_transaction,
            reverse_transaction,
        )
        if action == "ledger":
            return get_ledger(ticker=ticker or None, limit=limit, workspace=WORKSPACE)
        elif action == "add":
            return add_transaction(
                ticker=ticker,
                action=trade_action,
                quantity=quantity,
                price=price,
                fee=fee,
                asset_type=asset_type or None,
                workspace=WORKSPACE,
            )
        elif action == "reverse":
            return reverse_transaction(tx_id=tx_id, reason=reason, workspace=WORKSPACE)
    elif action in ["approve", "reject", "list_pending"]:
        from praxis.tools.ledger import (
            approve_transaction,
            reject_transaction,
            list_pending_transactions,
        )
        if action == "approve":
            return approve_transaction(tx_id=tx_id, workspace=WORKSPACE)
        elif action == "reject":
            return reject_transaction(tx_id=tx_id, reason=reason, workspace=WORKSPACE)
        elif action == "list_pending":
            return list_pending_transactions(workspace=WORKSPACE)
    elif action in ["get", "list", "create"]:
        from praxis.tools.decision import (
            get_decision,
            list_decisions,
            create_decision,
        )
        if action == "get":
            return get_decision(decision_id=tx_id, workspace=WORKSPACE)
        elif action == "list":
            return list_decisions(status=status or None, limit=limit, workspace=WORKSPACE)
        elif action == "create":
            return create_decision(
                ticker=ticker,
                action=decision_action,
                confidence=confidence,
                reasoning=reasoning,
                workspace=WORKSPACE,
            )


async def market_data_ext_tool(
    action: str,  # fund_flow / dragon_tiger / research
    ticker: str = "",
    days: int = 5,
    limit: int = 20,
    rating: str = "",
) -> dict:
    """扩展行情数据（整合 4 个工具）

    Args:
        action: 操作类型
            - fund_flow: 资金流向（min/daily/all）
            - dragon_tiger: 龙虎榜（list/detail）
            - research: 研报（list/eps）
        ticker: 标的代码
        days: 历史天数
        limit: 返回数量
        rating: 评级过滤

    Returns:
        扩展行情数据
    """
    # 参数验证
    if action not in ["fund_flow", "dragon_tiger", "research"]:
        return {
            "success": False,
            "error_code": "INVALID_ACTION",
            "error": ERROR_CODES["INVALID_ACTION"].format(action=action),
        }

    # 路由到具体实现
    if action == "fund_flow":
        from praxis.tools.fund_flow import get_fund_flow_daily
        return await get_fund_flow_daily(ticker=ticker, days=days)
    elif action == "dragon_tiger":
        from praxis.tools.dragon_tiger import get_dragon_tiger_list
        return await get_dragon_tiger_list(limit=limit)
    elif action == "research":
        from praxis.tools.research_report import get_report_list
        return await get_report_list(ticker=ticker, limit=limit, rating=rating or None)


# ═══════════════════════════════════════════════════════════════════
async def cascade_review_tool(
    mode: str,  # monthly / quarterly / annual
    investor: str = "demo",
    portfolio: str = "core",
    period: str = "",  # YYYY-MM / YYYY-Qx / YYYY，必填
) -> dict:
    """级联复盘路由（monthly/quarterly/annual）

    daily/weekly 模式已废弃，请使用单工具串行调用。
    详见 SOP_INDEX.md

    Args:
        mode: 复盘模式
            - monthly: 月度复盘（纪律代价 + 绩效 + 净值）
            - quarterly: 季度复盘（3个月聚合 + 进化评估）
            - annual: 年度复盘（12个月 + 铁律审计 + 重塑建议）
        investor: 投资者 ID
        portfolio: 组合 ID
        period: 时间范围
            - monthly: YYYY-MM (如 2026-06)
            - quarterly: YYYY-Qx (如 2026-Q2)
            - annual: YYYY (如 2026)

    Returns:
        复盘数据
    """
    # 参数验证
    if mode not in ["monthly", "quarterly", "annual"]:
        return {
            "success": False,
            "error_code": "INVALID_ACTION",
            "error": f"cascade_review_tool 仅支持 monthly/quarterly/annual。daily/weekly 已废弃，请使用单工具串行调用。详见 SOP_INDEX.md",
        }

    # 路由到具体实现
    if mode == "monthly":
        if not period:
            return {"success": False, "error": "monthly 模式需要 period 参数 (如 2026-06)"}
        from praxis.tools.review import generate_monthly_report
        return generate_monthly_report(period=period, investor=investor, portfolio=portfolio, workspace=WORKSPACE)
    elif mode == "quarterly":
        if not period:
            return {"success": False, "error": "quarterly 模式需要 period 参数 (如 2026-Q2)"}
        from praxis.tools.review import generate_quarterly_report
        return generate_quarterly_report(quarter=period, investor=investor, portfolio=portfolio, workspace=WORKSPACE)
    elif mode == "annual":
        if not period:
            return {"success": False, "error": "annual 模式需要 period 参数 (如 2026)"}
        from praxis.tools.review import generate_annual_report
        return generate_annual_report(year=period, investor=investor, portfolio=portfolio, workspace=WORKSPACE)


# ═══════════════════════════════════════════════════════════════════
# MCP Resource
# ═══════════════════════════════════════════════════════════════════

@mcp.resource("praxis://workspace/discovery")
def workspace_discovery_resource() -> dict:
    """Workspace 元数据（MCP Resource）：支持 Resources 协议的客户端可在连接握手时自动读取。"""
    from praxis.tools.workspace import discover_workspace
    return discover_workspace(WORKSPACE)


# ═══════════════════════════════════════════════════════════════════
# 分层注册 + 启动
# ═══════════════════════════════════════════════════════════════════

def _register_tools():
    """根据 PRAXIS_TOOLS_TIER 环境变量注册对应层级的工具。

    取值: core（默认） / advanced / admin / all
      core     = 核心工具（日常监控 + 交易）
      advanced = core + 高级工具（策略进化、回测）
      admin    = 全部工具（含投资者初始化、配置管理）
      all      = 全部工具（含 deprecated，用于向后兼容）
    """
    tier = os.environ.get("PRAXIS_TOOLS_TIER", "core").lower()
    max_tier = _TIER_ORDER.get(tier, 2)
    include_deprecated = tier == "all"

    # 收集模块命名空间中已定义的函数
    import sys
    module_ns = sys.modules[__name__]

    registered_count = 0
    skipped_count = 0

    for tool_name, tool_info in _TOOLS_TIER.items():
        if isinstance(tool_info, dict):
            tool_tier = tool_info.get("tier", "core")
            is_deprecated = tool_info.get("deprecated", False)
        else:
            tool_tier = tool_info
            is_deprecated = False
        
        # 跳过 deprecated 工具（除非明确要求包含）
        if is_deprecated and not include_deprecated:
            skipped_count += 1
            continue
        
        if _TIER_ORDER.get(tool_tier, 2) <= max_tier:
            fn = getattr(module_ns, tool_name, None)
            if fn is not None:
                if is_deprecated:
                    # 添加 deprecated 标记
                    fn = _add_deprecated_tag(fn)
                mcp.add_tool(fn)
                registered_count += 1

    print(f"✅ 已注册 {registered_count} 个工具（跳过 {skipped_count} 个 deprecated 工具）")


def _add_deprecated_tag(fn):
    """为 deprecated 工具添加警告标记"""
    original_doc = fn.__doc__ or ""
    fn.__doc__ = f"[Deprecated] 此工具已在 v4.0.0 中彻底废弃。\n\n{original_doc}"
    return fn


def main():
    """启动 MCP Server"""
    # 初始化健康检查器
    from praxis.health_checker import initialize_health_checker
    asyncio.run(initialize_health_checker())
    
    _register_tools()
    
    # 获取传输层配置（默认 stdio 模式）
    transport = os.environ.get("PRAXIS_TRANSPORT", "stdio").lower()
    
    if transport == "sse":
        # SSE 模式：监听本地端口
        host = os.environ.get("PRAXIS_HOST", "127.0.0.1")
        port = int(os.environ.get("PRAXIS_PORT", "8080"))
        print(f"🚀 启动 MCP Server (SSE 模式): http://{host}:{port}")
        mcp.run(transport="sse", host=host, port=port)
    else:
        # stdio 模式：默认
        print("🚀 启动 MCP Server (stdio 模式)")
        mcp.run()


if __name__ == "__main__":
    main()
