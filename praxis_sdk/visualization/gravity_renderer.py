"""
Praxis PDA 引力带可视化 (Gravity Heatmap)
将标的价格在 MA10/MA20/MA30 支撑带中的位置渲染为 ASCII 力场

用法：
  python praxis_sdk/visualization/gravity_renderer.py --ticker 600522 --price 50.20 --ma10 52.30 --ma20 50.10 --ma30 48.50
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MABands:
    """均线支撑带"""
    ma10: float
    ma20: float
    ma30: float
    current_price: float


@dataclass
class GravityResult:
    """引力场计算结果"""
    ticker: str
    current_price: float
    nearest_support: str  # "MA10" | "MA20" | "MA30"
    distance_pct: float  # 距最近支撑位的百分比
    gravity_level: str  # "远" | "近" | "进入"
    zone: str  # "弱引力区" | "中引力区" | "强引力买入区"
    ascii_chart: str  # ASCII 力场图
    is_resistance: bool = False  # 是否为阻力位（价格跌破所有均线）
    trend_warning: Optional[str] = None  # 破位预警


class GravityRenderer:
    """PDA 引力带渲染器"""
    
    def calculate(self, ticker: str, ma_bands: MABands) -> GravityResult:
        """
        计算现价在均线支撑带中的位置。
        
        Returns:
            GravityResult with nearest_support, distance_pct, gravity_level, zone, ascii_chart
        """
        price = ma_bands.current_price
        ma10 = ma_bands.ma10
        ma20 = ma_bands.ma20
        ma30 = ma_bands.ma30
        
        # 检查价格是否有效
        if price <= 0 or ma10 <= 0 or ma20 <= 0 or ma30 <= 0:
            return GravityResult(
                ticker=ticker,
                current_price=price,
                nearest_support="N/A",
                distance_pct=0,
                gravity_level="无数据",
                zone="价格无效",
                ascii_chart=f"价格引力场 — {ticker}\n  价格数据无效",
                is_resistance=False,
                trend_warning=None
            )
        
        # 找最近的均线（可能是支撑也可能是阻力）
        distances = {
            "MA10": abs(price - ma10) / ma10 * 100,
            "MA20": abs(price - ma20) / ma20 * 100,
            "MA30": abs(price - ma30) / ma30 * 100,
        }
        nearest = min(distances, key=distances.get)
        distance_pct = distances[nearest]
        
        # 判断是否为阻力位（价格跌破所有均线）
        is_resistance = price < ma10 and price < ma20 and price < ma30
        
        # 判断引力等级和区域
        if is_resistance:
            # 价格跌破所有均线 → 阻力力场
            if distance_pct < 1.0:
                gravity_level = "进入"
                zone = "阻力力场（破位预警）"
            elif distance_pct < 3.0:
                gravity_level = "近"
                zone = "阻力区（谨慎观望）"
            else:
                gravity_level = "远"
                zone = "深度破位区"
        else:
            # 正常支撑力场
            if distance_pct < 1.0:
                gravity_level = "进入"
                zone = "强引力买入区"
            elif distance_pct < 3.0:
                gravity_level = "近"
                zone = "中引力区"
            else:
                gravity_level = "远"
                zone = "弱引力区"
        
        # 生成 ASCII 力场图
        ascii_chart = self._render_ascii(ticker, price, ma10, ma20, ma30, is_resistance)
        
        # 破位预警
        trend_warning = None
        if is_resistance:
            trend_warning = f"⚠️ {ticker} 已跌破所有均线，均线变为阻力位，谨慎接飞刀"
        
        return GravityResult(
            ticker=ticker,
            current_price=price,
            nearest_support=nearest,
            distance_pct=distance_pct,
            gravity_level=gravity_level,
            zone=zone,
            ascii_chart=ascii_chart,
            is_resistance=is_resistance,
            trend_warning=trend_warning
        )
    
    def _render_ascii(self, ticker: str, price: float, ma10: float, ma20: float, ma30: float,
                      is_resistance: bool = False) -> str:
        """渲染 ASCII 力场图"""
        items = [
            ("MA10", ma10),
            ("MA20", ma20),
            ("MA30", ma30),
            ("现价", price)
        ]
        
        # 排序均线和价格
        min_val = min(val for _, val in items)
        max_val = max(val for _, val in items)
        
        # 按照数值从大到小排序（价格高的在最上面）
        items.sort(key=lambda x: x[1], reverse=True)
        
        # 计算每个值在 30 字符宽度中的位置
        width = 30
        def to_pos(val):
            if max_val == min_val:
                return width // 2
            return int((val - min_val) / (max_val - min_val) * (width - 1))
        
        # 生成每一行
        lines = []
        for name, val in items:
            pos = to_pos(val)
            
            if name == "现价":
                price_line = " " * pos + "★"
                if is_resistance:
                    lines.append(f"  {name:4} {price_line} {val:.2f} ⚠️ 破位")
                else:
                    lines.append(f"  {name:4} {price_line} {val:.2f}")
            else:
                line = " " * pos + "━" * (width - pos)
                if is_resistance:
                    label = f"  ← 阻力位"
                elif name == "MA30":
                    label = f"  ← 强引力（买入区）"
                elif name == "MA20":
                    label = f"  ← 中引力"
                else:
                    label = f"  ← 弱引力"
                
                lines.append(f"  {name:4} {line} {val:.2f}{label}")
        
        title = f"阻力力场" if is_resistance else "价格引力场"
        return f"{title} — {ticker}\n" + "\n".join(lines)
    
    def render_for_output(self, ticker: str, ma_bands: MABands) -> str:
        """
        生成适合 Skill 输出的引力场描述（去术语化）。
        
        Returns:
            支撑场景："600522 距离 MA30 支撑位 48.50 还有 3.4%，进入高引力买入区"
            阻力场景："600522 已跌破所有均线，均线变为阻力位，谨慎接飞刀"
        """
        result = self.calculate(ticker, ma_bands)
        
        # 阻力力场警告
        if result.is_resistance:
            return result.trend_warning
        
        # 正常支撑力场
        if result.gravity_level == "进入":
            return f"{ticker} 在 {result.nearest_support} 支撑位 {ma_bands.__dict__[result.nearest_support.lower()]:.2f} 附近，{result.zone}"
        elif result.gravity_level == "近":
            return f"{ticker} 距离 {result.nearest_support} 支撑位还有 {result.distance_pct:.1f}%，{result.zone}"
        else:
            return f"{ticker} 远离均线支撑，{result.zone}"


def main():
    """CLI 入口"""
    import argparse
    parser = argparse.ArgumentParser(description="PDA 引力带可视化")
    parser.add_argument("--ticker", type=str, required=True, help="标的代码")
    parser.add_argument("--price", type=float, required=True, help="当前价格")
    parser.add_argument("--ma10", type=float, required=True, help="MA10")
    parser.add_argument("--ma20", type=float, required=True, help="MA20")
    parser.add_argument("--ma30", type=float, required=True, help="MA30")
    args = parser.parse_args()
    
    renderer = GravityRenderer()
    ma_bands = MABands(ma10=args.ma10, ma20=args.ma20, ma30=args.ma30, current_price=args.price)
    result = renderer.calculate(args.ticker, ma_bands)
    
    print(result.ascii_chart)
    print(f"\n{renderer.render_for_output(args.ticker, ma_bands)}")


if __name__ == "__main__":
    main()
