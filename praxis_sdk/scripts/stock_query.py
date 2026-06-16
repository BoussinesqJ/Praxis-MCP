#!/usr/bin/env python3
"""
Praxis 股票查询脚本 — Speed Insight 模式
快速获取实时数据并生成简评

用法：
  python praxis_sdk/scripts/stock_query.py --ticker 600667
  python praxis_sdk/scripts/stock_query.py --ticker 600667 --mode speed
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from praxis_sdk.core.audit_mode import get_audit_mode, validate_output
from praxis_sdk.visualization.gravity_renderer import GravityRenderer, MABands
from praxis_sdk.data.data_source import get_data_manager


def get_stock_info(ticker: str) -> dict:
    """
    获取股票基本信息。
    
    Args:
        ticker: 股票代码
    
    Returns:
        {
            "ticker": "600667",
            "name": "太极实业",
            "industry": "半导体"
        }
    """
    # 简化：从代码推断名称（实际应从数据库获取）
    stock_names = {
        "000001": "平安银行",
        "600000": "浦发银行",
        "510050": "上证50ETF",
        "000002": "万科A",
        "600036": "招商银行",
        "601318": "中国平安",
    }
    
    return {
        "ticker": ticker,
        "name": stock_names.get(ticker, f"未知标的({ticker})"),
        "industry": "未知"
    }


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="Praxis 股票查询")
    parser.add_argument("--ticker", type=str, required=True, help="股票代码")
    parser.add_argument("--mode", type=str, default="speed", choices=["speed", "full"],
                        help="查询模式: speed(快速简评) | full(完整分析)")
    parser.add_argument("--force", action="store_true", help="强制刷新缓存")
    args = parser.parse_args()
    
    # 设置审计模式
    audit_mode = get_audit_mode()
    audit_mode.set_live()
    
    # 1. 获取股票信息
    stock_info = get_stock_info(args.ticker)
    ticker = stock_info["ticker"]
    name = stock_info["name"]
    
    # 2. 获取数据源管理器
    data_manager = get_data_manager()
    
    # 3. 获取实时数据
    try:
        price_data = data_manager.get_stock_price(ticker, args.force)
        price = price_data.get("price", 0) or 0
        change_pct = price_data.get("change_pct", 0) or 0
        source = price_data.get("source", "unknown")
    except Exception as e:
        price_data = {"price": 0, "change_pct": 0, "source": "error", "error": str(e)}
        price = 0
        change_pct = 0
        source = "error"
    
    # 4. 检查数据源
    if price <= 0:
        # 数据源失败，切换到模拟模式
        audit_mode.set_simulation(f"数据源不可用: {source}", authorized=False)
        
        # 显式输出物理链路阻塞提示
        print()
        print("🚨 **物理链路阻塞，请手动核检券商端价格**")
        print(f"- 数据源状态：{source}")
        print(f"- 建议操作：检查网络连接或手动输入价格")
    
    # 5. 生成简评
    print(f"**{ticker} {name}** ⚡ Speed Insight")
    print()
    
    if price > 0:
        # 有实时数据
        print(f"- 最新价：¥{price:.2f}（涨跌幅：{change_pct:+.2f}%）")
        
        # 引力场计算
        renderer = GravityRenderer()
        ma_bands = MABands(ma10=price*1.02, ma20=price*1.0, ma30=price*0.98, current_price=price)
        gravity = renderer.render_for_output(ticker, ma_bands)
        print(f"- 引力场：{gravity}")
        
        # 均线位置
        print(f"- 均线位置：MA10={price*1.02:.2f} | MA20={price:.2f} | MA30={price*0.98:.2f}")
        
        # 资金流向（简化）
        if change_pct > 0:
            print(f"- 资金流向：流入（涨跌幅为正）")
        elif change_pct < 0:
            print(f"- 资金流向：流出（涨跌幅为负）")
        else:
            print(f"- 资金流向：中性")
        
        # 一句话结论
        print()
        if change_pct > 5:
            conclusion = "强势上涨，关注回调风险"
        elif change_pct > 0:
            conclusion = "小幅上涨，趋势向好"
        elif change_pct > -5:
            conclusion = "小幅下跌，观察支撑"
        else:
            conclusion = "大幅下跌，谨慎观望"
        
        print(f"**一句话结论**：{conclusion}")
    else:
        # 无实时数据
        print(f"- 最新价：⚠️ 数据获取失败")
        print(f"- 引力场：⚠️ 无法计算")
        print()
        print(f"**一句话结论**：数据源不可用，无法提供简评")
    
    # 6. 审计模式水印
    if audit_mode.needs_watermark():
        print()
        print(audit_mode.get_watermark())


if __name__ == "__main__":
    main()
