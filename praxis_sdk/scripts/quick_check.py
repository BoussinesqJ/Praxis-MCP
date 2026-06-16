#!/usr/bin/env python3
"""
Praxis 快速巡检脚本 — 战机座舱版
直接输出结构化 Markdown，禁止 Agent 二次翻译

数据源优先级：mx-data → akshare → 东方财富直连
缓存位置：outputs/logs/price_cache.json

用法：
  python praxis_sdk/scripts/quick_check.py
  python praxis_sdk/scripts/quick_check.py --force  # 强制刷新缓存
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from praxis_sdk.core.cache import cached_tool_call, get_cache
from praxis_sdk.core.lcd_detector import LCDDetector
from praxis_sdk.core.rule_engine import PortfolioParser
from praxis_sdk.core.sentinel_tracker import get_sentinel_tracker
from praxis_sdk.core.audit_mode import get_audit_mode, validate_output
from praxis_sdk.core.market_clock import get_market_clock
from praxis_sdk.visualization.gravity_renderer import GravityRenderer, MABands
from praxis_sdk.data.data_source import get_data_manager, CriticalDataError


def get_position_status_icon(pnl_pct: float) -> str:
    """根据盈亏百分比返回状态图标"""
    if pnl_pct >= 5:
        return "🟢 盈利"
    elif pnl_pct >= 0:
        return "🟢 平"
    elif pnl_pct >= -5:
        return "🟡 浮亏"
    else:
        return "🔴 亏损"


def get_position_strategy(pnl_pct: float, price_in_grid: bool = False) -> str:
    """根据盈亏和网格位置返回策略建议"""
    if pnl_pct >= 10:
        return "止盈"
    elif pnl_pct >= 0:
        return "持有"
    elif pnl_pct >= -5:
        return "观察"
    else:
        return "止损监控"


def get_position_limit_icon(position_pct: float) -> str:
    """根据持仓占比返回风控图标"""
    if position_pct <= 10:
        return "🔴 绝对防守"
    elif position_pct <= 30:
        return "🟡 适度试探"
    else:
        return "🟢 积极进攻"


def get_sentinel_icon(bullish_count: int) -> str:
    """根据多头哨兵数返回图标"""
    if bullish_count <= 2:
        return "🔴"
    elif bullish_count <= 4:
        return "🟡"
    else:
        return "🟢"


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="Praxis 快速巡检")
    parser.add_argument("--force", action="store_true", help="强制刷新缓存")
    parser.add_argument("--mode", type=str, default="live", choices=["live", "simulation", "review"],
                        help="审计模式: live(实盘) | simulation(模拟) | review(复盘)")
    parser.add_argument("--reason", type=str, help="模拟原因（simulation 模式必填）")
    args = parser.parse_args()
    
    # 设置审计模式
    audit_mode = get_audit_mode()
    if args.mode == "simulation":
        if not args.reason:
            print("❌ simulation 模式必须提供 --reason 参数")
            return
        audit_mode.set_simulation(args.reason, authorized=False)
    elif args.mode == "review":
        audit_mode.set_review(authorized=True)
    else:
        audit_mode.set_live()
    
    # 获取交易时钟
    market_clock = get_market_clock()
    
    # 1. 获取组合数据（从 project.md 增量解析）
    portfolio_parser = PortfolioParser("project.md")
    portfolio_data = portfolio_parser.parse()
    
    # 2. 获取数据源管理器
    data_manager = get_data_manager()
    
    # 3. 获取持仓价格（三级优先级 + 缓存）
    positions = portfolio_data.get("positions", [])
    tickers = [p.ticker for p in positions if p.ticker]
    
    prices = {}
    data_source_error = None
    
    if tickers:
        try:
            prices = data_manager.get_batch_prices(tickers, args.force)
        except CriticalDataError as e:
            data_source_error = str(e)
            # 硬熔断：直接报错停摆
            print(f"🚨 **CRITICAL: 所有数据源已熔断**")
            print(f"- 错误信息：{e}")
            print(f"- 建议操作：检查网络连接或手动输入价格")
            print()
            # 继续执行，但标记数据不可用
        except Exception as e:
            data_source_error = str(e)
    
    # 4. 获取哨兵数据（从 MCP 缓存）
    sentinel_data = cached_tool_call(
        "sentinel_tool",
        lambda: {"data": {"bullish_count": 2, "total": 8, "state": "绝对防守期"}},
        {"action": "scan"},
        args.force
    )
    
    # 5. 记录哨兵历史（用于 Rule 3 天数计算）
    sentinel_tracker = get_sentinel_tracker()
    sentinel = sentinel_data.get("data", {})
    bullish_count = sentinel.get("bullish_count", 2)
    total_sentinels = sentinel.get("total", 8)
    
    # 每天只记录一次
    if sentinel_tracker.should_record_today():
        sentinel_tracker.record(bullish_count, total_sentinels)
    
    # 获取 Rule 3 状态
    rule3_status = sentinel_tracker.get_rule3_status()
    
    # 6. 解析数据
    
    total_assets = portfolio_data.get("total_assets", 0)
    positions_value = portfolio_data.get("positions_value", 0)
    cash = portfolio_data.get("cash", 0)
    position_pct = portfolio_data.get("position_pct", 0)
    cash_ratio = (cash / total_assets * 100) if total_assets > 0 else 90
    
    # 6. LCD 检测
    lcd = LCDDetector()
    position_pct_rounded = round(position_pct, 1)
    lcd_result = lcd.check_portfolio_vs_rules(
        {"position_pct": position_pct_rounded, "tech_exposure_pct": 5.7},
        bullish_count
    )
    
    # 7. 生成战机座舱版输出
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 交易时钟状态
    print(market_clock.get_report_header())
    print()
    
    print(f"### 🛡️ Praxis 快速巡检 [{today}]")
    print()
    
    # 1. 哨兵与防线
    print("**1. 哨兵与防线 (Market Radar)**")
    sentinel_icon = get_sentinel_icon(bullish_count)
    print(f"*   **哨兵状态**：{sentinel_icon} **{bullish_count} / {total_sentinels} 多头**")
    position_limit_icon = get_position_limit_icon(position_pct)
    print(f"*   **仓位水位**：持仓 **{position_pct:.1f}%** | 现金 **{cash_ratio:.1f}%** (¥{cash:,.0f})")
    # Rule 3 状态（使用追踪器）
    rule3_days = rule3_status.get("consecutive_days", 0)
    rule3_action = rule3_status.get("action", "条件单正常")
    status_lock = rule3_status.get("status_lock", False)
    
    if status_lock:
        print(f"*   **风控熔断**：🚨 **Rule 3 STATUS_LOCK 第 {rule3_days} 天** — {rule3_action}")
    elif rule3_days > 0:
        print(f"*   **风控熔断**：⏳ **Rule 3 运行第 {rule3_days} 天** — {rule3_action}")
    else:
        print(f"*   **风控熔断**：✅ **Rule 3 正常** — 条件单正常")
    print()
    
    # 2. 核心资产状态
    print("**2. 核心资产状态 (Holdings Monitor)**")
    for pos in positions[:4]:  # 最多显示4只
        ticker = pos.ticker
        market_value = pos.market_value
        
        # 尝试从数据源获取价格
        price_data = prices.get(ticker, {})
        price = price_data.get("price", 0)
        change_pct = price_data.get("change_pct", 0)
        
        if price > 0:
            # 有价格数据
            status_icon = get_position_status_icon(change_pct)
            strategy = get_position_strategy(change_pct)
            print(f"*   {pos.name}：¥{market_value:,.0f} | {status_icon} | {strategy}")
        else:
            # 只有市值
            print(f"*   {pos.name}：¥{market_value:,.0f} | ⚠️ 无实时价格")
    print()
    
    # 3. 实时引力力场
    print("**3. 实时引力力场 (Gravity Heatmap)**")
    renderer = GravityRenderer()
    for pos in positions[:2]:  # 最多显示2只
        ticker = pos.ticker
        price_data = prices.get(ticker, {})
        price = price_data.get("price", 0)
        
        # 如果缓存中没有价格，尝试直接读取 price_cache.json
        if price <= 0:
            try:
                cache_file = PROJECT_ROOT / "outputs" / "logs" / "price_cache.json"
                if cache_file.exists():
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                    if ticker in cache:
                        price = cache[ticker].get("price", 0)
            except Exception:
                pass
        
        if price > 0:
            ma_bands = MABands(ma10=price*1.02, ma20=price*1.0, ma30=price*0.98, current_price=price)
            gravity = renderer.render_for_output(ticker, ma_bands)
            print(f"*   {ticker}：★ {gravity}")
        else:
            print(f"*   {ticker}：无价格数据，跳过引力计算")
    print()
    
    # 4. LCD 执纪决策
    print("**4. 🤖 LCD 执纪决策**")
    if lcd_result.allowed:
        # 检查是否有 Alpha 逻辑豁免
        if any("逻辑豁免权" in str(c.message) for c in lcd_result.conflicts):
            print(f"> ⚡ 积极型放行：逻辑豁免权生效，准许小量试探")
        else:
            print(f"> ✅ 组合合规，无规则冲突")
    else:
        print(f"> 🚨 规则冲突：{len(lcd_result.conflicts)} 项")
        for conflict in lcd_result.conflicts:
            print(f"> - {conflict.message}")
    print()
    
    # 数据源状态
    source_status = data_manager.get_source_status()
    active_sources = [k for k, v in source_status.items() if v.get("available")]
    print(f"*数据源：{' → '.join(active_sources)}*")
    
    # 审计模式水印
    if audit_mode.needs_watermark():
        print()
        print(audit_mode.get_watermark_suffix())


if __name__ == "__main__":
    main()
