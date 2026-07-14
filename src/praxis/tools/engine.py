"""MCP 工具 - 引擎（对账/约束检查）"""
from __future__ import annotations

import json

from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.data.provider import CachedDataProvider
from praxis.engine.reconciliation import ReconciliationEngine
from praxis.engine.constraint_checker import SimpleConstraintChecker

# ─── YamlConfigLoader 缓存：避免每次重复 YAML 解析 ───
_loader_cache: dict[str, YamlConfigLoader] = {}


def _get_loader(workspace: str = ".") -> YamlConfigLoader:
    """获取缓存的 YamlConfigLoader 实例"""
    if workspace not in _loader_cache:
        _loader_cache[workspace] = YamlConfigLoader(workspace)
    return _loader_cache[workspace]


def invalidate_loader_cache(workspace: str | None = None):
    """使缓存失效（配置变更时调用）"""
    if workspace:
        _loader_cache.pop(workspace, None)
    else:
        _loader_cache.clear()


async def reconcile(
    action: str = "dry_run",
    investor: str = "default",
    portfolio: str = "core",
    nav: float | None = None,
    quotes_json: str = "",
    workspace: str = ".",
    provider: CachedDataProvider | None = None,
) -> dict:
    """对账路由

    Args:
        action: dry_run（内部对账）/ external（外部数据对账）
        provider: 可选的全局 CachedDataProvider 实例。为 None 时自动创建新实例。
    """
    if action == "external":
        return await reconcile_external(quotes_json, investor, portfolio, workspace)

    # dry_run 模式
    loader = _get_loader(workspace)
    own_provider = provider is None
    if provider is None:
        provider = CachedDataProvider()
    try:
        engine = ReconciliationEngine(loader, provider)
        state = await engine.reconcile(investor, portfolio, nav=nav, dry_run=True)
        formatted = engine.format_state(state)
        return {
            "success": True,
            "data": {
                "state": state.model_dump(mode="json"),
                "formatted": formatted,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if own_provider:
            await provider.close()


def check_constraints(investor: str, portfolio: str, action: str, ticker: str, amount: float = 0, workspace: str = ".", _deps: dict | None = None) -> dict:
    """检查约束（策略驱动）"""
    # 从 _deps 获取正确的 workspace（MCP 进程中 CWD 可能是 praxis-mcp 目录）
    if _deps:
        workspace = _deps.get("workspace", workspace)
    loader = _get_loader(workspace)
    try:
        inv = loader.load_investor(investor)
        port = loader.load_portfolio(investor, portfolio)

        # 加载策略规则（策略驱动约束）
        strategy = None
        if port.strategy_template:
            try:
                strategy = loader.load_strategy(port.strategy_template)
            except Exception:
                pass  # 策略文件不存在时降级为无策略模式

        from praxis.core.models import PortfolioState, CashState
        state = PortfolioState(
            investor_id=investor,
            portfolio_id=portfolio,
            total_assets=inv.capital_cny,
            cash=CashState(
                total_cash=inv.capital_cny,
                available_cash=inv.capital_cny,
                frozen_cash=0,
            ),
        )
        checker = SimpleConstraintChecker(inv, port, strategy=strategy)
        results = checker.check(state, action, ticker, amount=amount)
        return {
            "success": True,
            "data": {
                "checks": results,
                "all_passed": all(r["passed"] for r in results),
                "blocked": [r for r in results if not r["passed"] and r["level"] == "hard_block"],
                "strategy_loaded": strategy.strategy_name if strategy else None,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def reconcile_external(
    quotes_json: str,
    investor: str = "default",
    portfolio: str = "core",
    workspace: str = ".",
) -> dict:
    """使用外部传入的行情数据对账（数据解耦）

    不需要自行采集行情，直接使用 WorkBuddy 传入的 realtime JSON，
    调用 ReconciliationEngine.reconcile_with_quotes() 执行对账计算。

    Args:
        quotes_json: 外部行情 JSON 字符串，结构应符合 QuotesPayload schema
        investor: 投资者 ID（默认 "default"）
        portfolio: 组合 ID（默认 "core"）
        workspace: 工作区路径

    Returns:
        对账结果，结构和 reconcile() 一致
    """
    # 空检查
    if not quotes_json or not quotes_json.strip():
        return {"success": False, "error": "缺少外部行情数据"}

    # JSON 解析
    try:
        raw = json.loads(quotes_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}"}

    # Pydantic 校验
    from praxis.core.schemas import QuotesPayload

    try:
        payload = QuotesPayload.model_validate(raw)
    except Exception as e:
        return {"success": False, "error": f"行情数据校验失败: {e}"}

    # 提取 {ticker: price} 字典
    quotes_dict: dict[str, float] = {}
    for ticker, item in payload.quotes.items():
        # item 是 QuoteItem（已由 Pydantic 转换）或 dict
        if hasattr(item, "price"):
            quotes_dict[ticker] = item.price
        elif isinstance(item, dict):
            quotes_dict[ticker] = float(item.get("price", 0))
        else:
            quotes_dict[ticker] = 0.0

    loader = _get_loader(workspace)
    engine = ReconciliationEngine(loader, None)  # 不依赖 DataProvider
    state = engine.reconcile_with_quotes(quotes_dict, investor, portfolio)
    formatted = engine.format_state(state)

    return {
        "success": True,
        "data": {
            "state": state.model_dump(mode="json"),
            "formatted": formatted,
        },
    }
