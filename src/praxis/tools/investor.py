"""MCP 工具 — 投资者管理（初始化 / 批量导入）

解决配置文件"鸡生蛋"死循环：
- create: 一步创建投资者 profile.yaml + 组合 portfolio.yaml
- init: 完整初始化（profile + portfolio + 开仓交易写入 ledger）
- list: 列出所有已创建的投资者
"""
from __future__ import annotations

import yaml
from datetime import datetime
from pathlib import Path

from praxis.agents.base import Tool
from praxis.engine.config_loader import _check_config_id
from praxis.core.models import Transaction, TransactionType, TransactionStatus


async def investor(
    action: str,  # "create" | "init" | "list"
    investor_id: str = "",
    name: str = "",
    capital_cny: float = 0.0,
    risk_level: str = "C3",
    style: str = "balanced",
    max_drawdown_pct: float = 20,
    portfolio_id: str = "core",
    strategy_type: str = "grid_value",
    strategy_template: str = "grid_value",
    positions: list[dict] | None = None,
    cash: float = 0.0,
    benchmark: str | None = None,
    _deps: dict | None = None,
) -> dict:
    """投资者管理

    Args:
        action: 操作类型 — create | init | list
        investor_id: 投资者 ID（目录名）
        name: 投资者名称
        capital_cny: 初始资金（人民币）
        risk_level: 风险等级（C1-C5）
        style: 投资风格
        max_drawdown_pct: 最大回撤容忍度(%)
        portfolio_id: 组合 ID
        strategy_type: 策略类型
        strategy_template: 策略模板名称
        positions: 持仓列表 [{ticker, name, quantity, avg_cost, type, category}]
        cash: 现金余额（init 时使用）
        benchmark: 基准指数代码（可选）

    Returns:
        {"success": bool, "data": ..., "error": str|None}
    """
    ws = Path(_deps.get("workspace", ".")) if _deps else Path(".")
    investors_dir = ws / "config" / "investors"

    if action == "list":
        try:
            if not investors_dir.exists():
                return {"success": True, "data": {"investors": []}}

            result = []
            for d in sorted(investors_dir.iterdir()):
                if not d.is_dir() or d.name.startswith(("_", ".")):
                    continue
                profile_path = d / "profile.yaml"
                if profile_path.exists():
                    try:
                        with open(profile_path, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                        inv_data = data.get("investor", {})
                        result.append({
                            "investor_id": d.name,
                            "name": inv_data.get("name", d.name),
                            "capital_cny": inv_data.get("capital_cny", 0),
                            "risk_level": inv_data.get("risk_level", ""),
                        })
                    except Exception:
                        result.append({
                            "investor_id": d.name,
                            "name": d.name,
                            "capital_cny": 0,
                        })
            return {"success": True, "data": {"investors": result, "count": len(result)}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # create / init 验证必要参数
    if not investor_id or not name:
        return {"success": False, "error": "action=create/init 需要 investor_id 和 name 参数"}
    if action == "init" and (not positions or cash <= 0):
        return {"success": False, "error": "action=init 需要 positions 和 cash 参数"}

    try:
        _check_config_id("investor_id", investor_id)
    except Exception as e:
        return {"success": False, "error": str(e)}

    try:
        _check_config_id("portfolio_id", portfolio_id)
    except Exception as e:
        return {"success": False, "error": str(e)}

    # ========== 1. 创建投资者 profile.yaml ==========
    profile_dir = investors_dir / investor_id
    profile_path = profile_dir / "profile.yaml"

    if profile_path.exists():
        return {
            "success": False,
            "error": f"投资者 {investor_id} 已存在: {profile_path}",
        }

    profile_dir.mkdir(parents=True, exist_ok=True)

    profile_data = {
        "investor": {
            "name": name,
            "id": investor_id,
            "capital_cny": capital_cny,
            "risk_level": risk_level,
            "style": style,
            "max_drawdown_pct": max_drawdown_pct,
        },
        "constraints": {
            "banned_markets": [],
            "banned_instruments": ["leverage", "options", "short"],
            "etf_exemption": True,
        },
        "execution": {
            "offshore_fund_window": "14:45-14:55",
            "intraday_open_blackout_minutes": 15,
            "min_transaction_cny": 3000,
        },
    }

    with open(profile_path, "w", encoding="utf-8") as f:
        yaml.dump(profile_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    results = [f"✓ 投资者画像: {investor_id}"]

    # ========== 2. 创建组合 portfolio.yaml ==========
    portfolio_dir = investors_dir / investor_id / "portfolios" / portfolio_id
    portfolio_path = portfolio_dir / "portfolio.yaml"

    if portfolio_path.exists():
        return {
            "success": False,
            "error": f"组合 {investor_id}/{portfolio_id} 已存在",
        }

    portfolio_dir.mkdir(parents=True, exist_ok=True)

    # 构建 assets 列表
    assets = []
    total_position_cost = 0.0
    for pos in (positions or []):
        ticker = pos["ticker"]
        asset_type = pos.get("type", "stock")
        category = pos.get("category", "other")
        avg_cost = pos.get("avg_cost", 0)
        quantity = pos.get("quantity", 0)
        total_position_cost += avg_cost * quantity

        target_weight = round((avg_cost * quantity) / capital_cny * 100, 1) if capital_cny > 0 else 0

        assets.append({
            "ticker": ticker,
            "name": pos.get("name", ticker),
            "type": asset_type,
            "category": category,
            "target_weight_pct": target_weight,
            "base_price": avg_cost,
        })

    portfolio_data = {
        "portfolio": {
            "strategy_type": strategy_type,
            "strategy_template": strategy_template,
            "base_currency": "CNY",
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "version": "v1.0",
            "description": f"{name} 的 {portfolio_id} 组合",
        },
        "assets": assets,
        "sentinels": {"macro_layer": [], "execution_layer": []},
    }

    with open(portfolio_path, "w", encoding="utf-8") as f:
        yaml.dump(portfolio_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    results.append(f"✓ 组合配置: {portfolio_id}（{len(assets)} 个资产）")

    # ========== 3. init 专属：写入 opening BUY 到 ledger ==========
    tx_ids = []
    if action == "init":
        ledger = _deps.get("ledger") if _deps else None
        if ledger is None:
            return {"success": False, "error": "Ledger未注入，init 需要 _deps['ledger']"}

        for pos in (positions or []):
            tx = Transaction(
                tx_id="",
                ticker=pos["ticker"],
                tx_type=TransactionType.BUY,
                quantity=pos["quantity"],
                price=pos["avg_cost"],
                fee=0.0,
                status=TransactionStatus.EXECUTED,
                idempotency_key=f"opening-{investor_id}-{pos['ticker']}",
                reason=f"Opening position: {pos.get('name', pos['ticker'])}",
                tags=["opening", "migration"],
                asset_type=pos.get("type", "stock"),
                investor_id=investor_id,
                portfolio_id=portfolio_id,
            )
            tx_id = ledger.append(tx)
            tx_ids.append(tx_id)

        results.append(f"✓ 开仓交易: {len(tx_ids)} 笔已写入 ledger")

    if action == "init":
        cash_ratio = cash / capital_cny * 100 if capital_cny > 0 else 0
        return {
            "success": True,
            "data": {
                "investor_id": investor_id,
                "portfolio_id": portfolio_id,
                "steps": results,
                "summary": {
                    "total_capital": capital_cny,
                    "total_invested": round(total_position_cost, 2),
                    "cash": round(cash, 2),
                    "cash_ratio": f"{cash_ratio:.1f}%",
                    "positions": len(positions or []),
                    "transaction_ids": tx_ids,
                    "benchmark": benchmark,
                },
                "message": (
                    f"投资者 {name}({investor_id}) 初始化完成\n"
                    f"总资产: ¥{capital_cny:,.2f} | "
                    f"持仓: {len(positions or [])} 只 | "
                    f"现金: ¥{cash:,.2f} ({cash_ratio:.1f}%)"
                ),
            },
        }

    return {
        "success": True,
        "data": {
            "investor_id": investor_id,
            "portfolio_id": portfolio_id,
            "profile_path": str(profile_path),
            "portfolio_path": str(portfolio_path),
            "assets_count": len(assets),
            "message": f"投资者 {name}({investor_id}) 及组合 {portfolio_id} 已创建",
        },
    }


def register(registry):
    registry.register(
        Tool(
            name="investor",
            description="投资者管理：create/init/list — 创建画像、组合、初始化持仓",
            handler=investor,
            agent_name="admin",
            tier="core",
        )
    )
