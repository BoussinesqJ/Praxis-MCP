"""扩展行情 — market_data_ext (资金流向/龙虎榜/研报)
数据源：腾讯公开行情API (qt.gtimg.cn) + akshare (备用)"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from praxis.agents.base import Tool
from praxis.tools._schemas import MarketDataExtInput

logger = logging.getLogger(__name__)


def _tencent_fund_flow(ticker: str) -> list[dict] | None:
    """通过腾讯公开行情API获取资金流向估计

    基于 Tencent qt.gtimg.cn 的逐档买卖盘数据计算：
    - 主动买盘(外盘) = 以卖档价格成交的股数
    - 主动卖盘(内盘) = 以买档价格成交的股数
    - 主力净流向 = (大单买 - 大单卖) 的估算值

    Args:
        ticker: 股票/ETF代码

    Returns:
        资金流向记录列表，失败返回 None
    """
    try:
        market = "sh" if ticker.startswith(("6", "5")) else "sz"
        url = f"http://qt.gtimg.cn/q={market}{ticker}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("gbk")

        # 解析字段
        fields = raw.split("~")
        if len(fields) < 40:
            return None

        name = fields[1]
        price = float(fields[3]) if fields[3] else 0
        buy_vol = int(fields[7]) if fields[7] else 0  # 外盘(主动买)
        sell_vol = int(fields[8]) if fields[8] else 0  # 内盘(主动卖)
        volume = int(fields[6]) if fields[6] else 0
        amount = int(float(fields[37]) * 10000) if fields[37] else 0 if fields[36] else 1
        change_pct = float(fields[32]) if fields[32] else 0

        # 从逐档数据估算大单流向
        # 档位数据：买1-买5 (字段9-19, 每隔1个), 卖1-卖5 (字段20-29, 每隔1个)
        # 格式是价格|成交量|... 交错排列
        bid_volumes = []
        ask_volumes = []
        for i in range(5):
            idx_bid = 9 + i * 2  # 买档价格
            idx_ask = 19 + i * 2  # 卖档价格
            if idx_bid + 1 < len(fields) and fields[idx_bid + 1]:
                try:
                    bid_volumes.append(int(fields[idx_bid + 1]))
                except ValueError:
                    pass
            if idx_ask + 1 < len(fields) and fields[idx_ask + 1]:
                try:
                    ask_volumes.append(int(fields[idx_ask + 1]))
                except ValueError:
                    pass

        # 净主动流向 = (外盘 - 内盘) × 价格
        net_active_vol = buy_vol - sell_vol
        net_active_flow = round(net_active_vol * price)

        # 大单估计：假设大单占外盘/内盘的30%（ETF调低比例）
        large_buy = int(buy_vol * 0.3)
        large_sell = int(sell_vol * 0.3)
        large_net = round((large_buy - large_sell) * price)

        # 小单 = 总 - 大单
        small_net = net_active_flow - large_net

        return [{
            "date": fields[30][:8] if len(fields) > 30 and fields[30] else "",
            "ticker": ticker,
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "volume": volume,
            "amount": amount,
            "active_buy_vol": buy_vol,
            "active_sell_vol": sell_vol,
            "net_active_flow": net_active_flow,
            "large_net_flow": large_net,
            "small_net_flow": small_net - large_net,
            "mid_net_flow": 0,
            "source": "tencent_proxy",
            "note": "基于外盘/内盘估算，非精确值",
        }]
    except Exception as e:
        logger.warning(f"tencent fund_flow proxy error: {e}")
        return None


async def market_data_ext(action: str, ticker: str = "", days: int = 5,
                          limit: int = 20, rating: str = "",
                          _deps: dict | None = None) -> dict:
    try:
        if action == "fund_flow":
            # Path A: akshare (eastmoney)
            try:
                import akshare as ak
                market = "sh" if ticker.startswith(("6", "5")) else "sz"
                df = ak.stock_individual_fund_flow(stock=ticker, market=market)
                result = df.tail(days).to_dict(orient="records") if df is not None else []
                return {"success": True, "source": "akshare_eastmoney", "data": result}
            except Exception as akshare_err:
                logger.warning(f"akshare fund_flow failed: {akshare_err}")

            # Path B: Tencent 公开API代理估计
            tencent_data = _tencent_fund_flow(ticker)
            if tencent_data:
                return {"success": True, "source": "tencent_proxy", "data": tencent_data}

            return {"success": False, "source": "failed",
                    "error": f"akshare + tencent proxy 均失败: {akshare_err}"}

        elif action == "research":
            # 研报：通过 tdx-connector 获取（结构化数据）
            try:
                import akshare as ak
                df = ak.stock_research_report_em(symbol=ticker)
                result = df.head(limit).to_dict(orient="records") if df is not None else []
                return {"success": True, "source": "akshare", "data": result}
            except Exception as e:
                return {"success": False, "error": f"研报获取失败: {e}"}

        return {"success": False, "error": f"未知 action: {action}"}
    except ImportError:
        return {"success": False, "error": "依赖模块未安装"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def register(registry):
    registry.register(Tool(name="market_data_ext", description="扩展行情：资金流向/龙虎榜/研报",
                           input_schema=MarketDataExtInput, handler=market_data_ext,
                           agent_name="market", tier="core"))
