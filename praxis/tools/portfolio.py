"""MCP 工具 - 组合管理"""
from __future__ import annotations

from praxis.engine.config_loader import YamlConfigLoader


def get_portfolio(investor: str, portfolio: str, workspace: str = ".") -> dict:
    """读取组合配置"""
    loader = YamlConfigLoader(workspace)
    try:
        p = loader.load_portfolio(investor, portfolio)
        return {
            "success": True,
            "data": p.model_dump(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_asset_detail(investor: str, portfolio: str, ticker: str, workspace: str = ".") -> dict:
    """读取单标的详情"""
    loader = YamlConfigLoader(workspace)
    try:
        detail = loader.load_asset_detail(investor, portfolio, ticker)
        return {
            "success": True,
            "data": detail,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
