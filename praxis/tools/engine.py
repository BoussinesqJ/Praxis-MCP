"""MCP 工具 - 引擎（对账/约束检查）"""
from __future__ import annotations

from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.data.provider import CachedDataProvider
from praxis.engine.reconciliation import ReconciliationEngine
from praxis.engine.constraint_checker import SimpleConstraintChecker


async def reconcile(investor: str, portfolio: str, nav: float | None = None, workspace: str = ".") -> dict:
    """对账（dry-run only）"""
    loader = YamlConfigLoader(workspace)
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
        await provider.close()


def check_constraints(investor: str, portfolio: str, action: str, ticker: str, amount: float = 0, workspace: str = ".") -> dict:
    """检查约束"""
    loader = YamlConfigLoader(workspace)
    try:
        inv = loader.load_investor(investor)
        port = loader.load_portfolio(investor, portfolio)
        from praxis.core.models.state import PortfolioState, CashState
        state = PortfolioState(
            investor_id=investor,
            portfolio_id=portfolio,
            cash=CashState(
                total_assets=inv.capital_cny,
                available_cash=inv.capital_cny,
                cash_ratio=1.0,
            ),
        )
        checker = SimpleConstraintChecker(inv, port)
        results = checker.check(state, action, ticker, amount=amount)
        return {
            "success": True,
            "data": {
                "checks": results,
                "all_passed": all(r["passed"] for r in results),
                "blocked": [r for r in results if not r["passed"] and r["level"] == "hard_block"],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
