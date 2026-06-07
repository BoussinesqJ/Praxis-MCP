"""MCP 工具 - 投资者管理（初始化 / 批量导入）

解决配置文件"鸡生蛋"死循环：
- create_investor: 创建投资者 profile.yaml
- create_portfolio: 创建组合 portfolio.yaml
- init_investor: 一条命令完成投资者+组合+持仓初始化
"""
from __future__ import annotations

import re
import yaml
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType, TransactionStatus
from praxis.core.validation import validate_id


def _investors_dir(workspace: str) -> Path:
    return Path(workspace) / "investors"


def create_investor(
    investor_id: str,
    name: str,
    capital_cny: float,
    risk_level: str = "C3",
    style: str = "balanced",
    max_drawdown_pct: float = 20,
    workspace: str = ".",
) -> dict:
    """创建投资者画像配置文件

    Args:
        investor_id: 投资者 ID（目录名）
        name: 投资者名称
        capital_cny: 初始资金（人民币）
        risk_level: 风险等级（C1-C5）
        style: 投资风格
        max_drawdown_pct: 最大回撤容忍度(%)
    """
    try:
        err = validate_id("investor_id", investor_id)
        if err:
            return {"success": False, "error": err}

        profile_dir = _investors_dir(workspace) / investor_id
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

        return {
            "success": True,
            "data": {
                "investor_id": investor_id,
                "profile_path": str(profile_path),
                "message": f"投资者 {name}({investor_id}) 画像已创建",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_portfolio(
    investor_id: str,
    portfolio_id: str,
    strategy_type: str = "grid_value",
    strategy_template: str = "grid_value",
    description: str | None = None,
    assets: list[dict] | None = None,
    workspace: str = ".",
) -> dict:
    """创建投资组合配置文件

    Args:
        investor_id: 投资者 ID
        portfolio_id: 组合 ID（目录名）
        strategy_type: 策略类型
        strategy_template: 策略模板名称
        description: 组合描述
        assets: 资产列表，每项包含 ticker/name/type/category/target_weight_pct
    """
    try:
        err = validate_id("investor_id", investor_id)
        if err:
            return {"success": False, "error": err}
        err = validate_id("portfolio_id", portfolio_id)
        if err:
            return {"success": False, "error": err}

        portfolio_dir = (
            _investors_dir(workspace) / investor_id / "portfolios" / portfolio_id
        )
        portfolio_path = portfolio_dir / "portfolio.yaml"

        if portfolio_path.exists():
            return {
                "success": False,
                "error": f"组合 {investor_id}/{portfolio_id} 已存在",
            }

        portfolio_dir.mkdir(parents=True, exist_ok=True)

        portfolio_data = {
            "portfolio": {
                "strategy_type": strategy_type,
                "strategy_template": strategy_template,
                "base_currency": "CNY",
                "created_at": datetime.now().strftime("%Y-%m-%d"),
                "version": "v1.0",
                "description": description or f"{portfolio_id} 组合",
            },
            "assets": assets or [],
            "sentinels": {"macro_layer": [], "execution_layer": []},
        }

        with open(portfolio_path, "w", encoding="utf-8") as f:
            yaml.dump(portfolio_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return {
            "success": True,
            "data": {
                "investor_id": investor_id,
                "portfolio_id": portfolio_id,
                "portfolio_path": str(portfolio_path),
                "message": f"组合 {portfolio_id} 已创建（{len(assets or [])} 个资产）",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def init_investor(
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
    workspace: str = ".",
) -> dict:
    """一条命令完成投资者+组合+持仓初始化

    自动完成：
    1. 创建 investors/{id}/profile.yaml
    2. 创建 investors/{id}/portfolios/{pid}/portfolio.yaml
    3. 为每个持仓写入一笔 opening BUY 交易到 ledger

    Args:
        investor_id: 投资者 ID
        investor_name: 投资者名称
        capital_cny: 初始总资金
        portfolio_id: 组合 ID
        positions: 持仓列表，每项: {ticker, name, quantity, avg_cost, type, category}
        cash: 当前现金余额
        risk_level: 风险等级
        style: 投资风格
        max_drawdown_pct: 最大回撤容忍度(%)
        strategy_type: 策略类型
        strategy_template: 策略模板名称
        benchmark: 基准指数代码（可选）
    """
    try:
        results = []

        # 1. 创建投资者画像
        profile_result = create_investor(
            investor_id=investor_id,
            name=investor_name,
            capital_cny=capital_cny,
            risk_level=risk_level,
            style=style,
            max_drawdown_pct=max_drawdown_pct,
            workspace=workspace,
        )
        if not profile_result["success"]:
            # 如果已存在，尝试继续（可能是重试）
            if "已存在" not in profile_result.get("error", ""):
                return profile_result
        results.append(f"✓ 投资者画像: {investor_id}")

        # 2. 构建资产列表并创建组合
        assets = []
        total_position_cost = 0
        for pos in positions:
            ticker = pos["ticker"]
            asset_type = pos.get("type", "stock")
            category = pos.get("category", "other")
            avg_cost = pos["avg_cost"]
            quantity = pos["quantity"]
            total_position_cost += avg_cost * quantity

            # 推算目标权重
            target_weight = round((avg_cost * quantity) / capital_cny * 100, 1) if capital_cny > 0 else 0

            assets.append({
                "ticker": ticker,
                "name": pos.get("name", ticker),
                "type": asset_type,
                "category": category,
                "target_weight_pct": target_weight,
                "base_price": avg_cost,
            })

        portfolio_result = create_portfolio(
            investor_id=investor_id,
            portfolio_id=portfolio_id,
            strategy_type=strategy_type,
            strategy_template=strategy_template,
            description=f"{investor_name} 的 {portfolio_id} 组合",
            assets=assets,
            workspace=workspace,
        )
        if not portfolio_result["success"]:
            if "已存在" not in portfolio_result.get("error", ""):
                return portfolio_result
        results.append(f"✓ 组合配置: {portfolio_id}（{len(assets)} 个资产）")

        # 3. 写入 opening positions 到 ledger
        ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
        ledger = FileLedger(ledger_path)
        tx_ids = []

        for pos in positions:
            tx = Transaction(
                tx_id="",
                type=TransactionType.BUY,
                ticker=pos["ticker"],
                quantity=pos["quantity"],
                price=pos["avg_cost"],
                fee=0,
                status=TransactionStatus.CONFIRMED,
                idempotency_key=f"opening-{investor_id}-{pos['ticker']}",
                notes=f"Opening position: {pos.get('name', pos['ticker'])}",
                tags=["opening", "migration"],
                asset_type=pos.get("type"),
            )
            tx_id = ledger.append(tx)
            tx_ids.append(tx_id)

        results.append(f"✓ 开仓交易: {len(tx_ids)} 笔已写入 ledger")

        # 汇总
        total_invested = total_position_cost
        cash_ratio = cash / capital_cny * 100 if capital_cny > 0 else 0

        return {
            "success": True,
            "data": {
                "investor_id": investor_id,
                "portfolio_id": portfolio_id,
                "steps": results,
                "summary": {
                    "total_capital": capital_cny,
                    "total_invested": round(total_invested, 2),
                    "cash": round(cash, 2),
                    "cash_ratio": f"{cash_ratio:.1f}%",
                    "positions": len(positions),
                    "transaction_ids": tx_ids,
                    "benchmark": benchmark,
                },
                "message": (
                    f"投资者 {investor_name}({investor_id}) 初始化完成\n"
                    f"总资产: ¥{capital_cny:,.2f} | "
                    f"持仓: {len(positions)} 只 | "
                    f"现金: ¥{cash:,.2f} ({cash_ratio:.1f}%)"
                ),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
