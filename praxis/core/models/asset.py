"""资产类型枚举"""
from __future__ import annotations

from enum import Enum


class AssetType(str, Enum):
    """资产类型（V1 实现 + 预留扩展）"""
    STOCK = "stock"                # A 股
    ETF = "etf"                    # ETF
    OFFSHORE_FUND = "offshore_fund"  # 场外基金
    UNKNOWN = "unknown"            # 未知（纯 ledger 推断模式时使用）
    # V1 不实现，预留扩展：
    # BOND = "bond"                # 债券
    # CONVERTIBLE_BOND = "convertible_bond"  # 可转债
    # HK_STOCK = "hk_stock"        # 港股
    # US_STOCK = "us_stock"        # 美股
    # CRYPTO = "crypto"            # 加密货币


class AssetCategory(str, Enum):
    """资产分类"""
    POWER_INFRA = "power_infra"          # 电力基础设施
    TECH_SATELLITE = "tech_satellite"    # 科技卫星
    BROAD_INDEX = "broad_index"          # 宽基指数
    INDUSTRY = "industry"                # 行业主题
    BOND = "bond"                        # 债券
    CASH = "cash"                        # 现金
    DEFENSIVE_BASE = "defensive_base"    # 防御宽基
    SCIENCE_BOARD = "science_board"      # 科创板
    OPTICAL_CABLE = "optical_cable"      # 海缆光通
    COAL_REFERENCE = "coal_reference"    # 煤炭参考
    GROWTH_SATELLITE = "growth_satellite"  # 成长卫星
    GROWTH_INDEX = "growth_index"          # 成长指数
    DIVIDEND = "dividend"                  # 红利
    GENERAL = "general"                    # 通用兜底
    UNKNOWN = "unknown"                    # 未知（纯 ledger 推断模式时使用）
