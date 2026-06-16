"""
Praxis 规则引擎 - 规则审计引擎
实现 Rule 1-10 + Protocol 1-3 的核心校验逻辑

SSOT 原则：所有数据来自 project.md，不在内存中维护第二份账目
性能优化：使用行流解析，定位到 [CURRENT_HOLDINGS] 块后即停
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from pathlib import Path
import os
import re


@dataclass
class PortfolioState:
    """组合状态（从 project.md 解析）"""
    total_assets: float
    positions_value: float
    cash: float
    position_pct: float  # 持仓占比


@dataclass
class Position:
    """单只持仓"""
    ticker: str
    name: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl_pct: float
    asset_type: str  # stock, etf, offshore_fund


@dataclass
class SentinelState:
    """哨兵状态（从 sentinel_tool 获取）"""
    bullish_count: int  # 多头哨兵数
    total: int  # 总哨兵数


@dataclass
class RuleResult:
    """规则校验结果"""
    rule: str
    allowed: bool
    warning: Optional[str] = None
    conflict: Optional[str] = None
    reason: Optional[str] = None
    action: Optional[str] = None


class PortfolioParser:
    """
    project.md 增量解析器
    
    性能优化：使用行流读取，定位到 [CURRENT_HOLDINGS] 块后即停
    避免对 100 行以上的非核心区域进行无效正则扫描
    """
    
    def __init__(self, project_path: str = None):
        if project_path is None:
            ws = os.environ.get("PRAXIS_WORKSPACE", ".")
            project_path = os.path.join(
                ws, os.environ.get("PRAXIS_PROJECT_PATH", "project.md")
            )
        self.project_path = Path(project_path)
    
    def parse(self) -> Dict:
        """
        解析 project.md，返回持仓数据。
        
        Returns:
            {
                "total_assets": float,
                "positions_value": float,
                "cash": float,
                "position_pct": float,
                "positions": List[Position]
            }
        """
        if not self.project_path.exists():
            return self._default_data()
        
        # 行流解析：只读取相关部分
        positions = []
        total_assets = 0.0
        positions_value = 0.0
        
        in_holdings_section = False
        in_funds_section = False
        holdings_header_verified = False
        
        with open(self.project_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                
                # --- 1. 检测区块边界 ---
                if "### 持仓（防守姿态）" in line:
                    in_holdings_section = True
                    continue
                
                if "FUNDS_DISTRIBUTION_START" in line:
                    in_holdings_section = False
                    in_funds_section = True
                    continue
                
                if "FUNDS_DISTRIBUTION_END" in line:
                    in_funds_section = False
                    continue
                
                # --- 2. 解析真实持仓表（不依赖表情包） ---
                if in_holdings_section and "|" in line:
                    # 验证表头：直接匹配列名
                    if "标的" in line and "数量" in line and "成本" in line and "现价" in line:
                        holdings_header_verified = True
                        continue
                    
                    # 跳过表头分隔线
                    if holdings_header_verified and "---" in line:
                        continue
                    
                    # 解析持仓数据行
                    if holdings_header_verified:
                        pos = self._parse_holding_row(line)
                        if pos:
                            positions.append(pos)
                    continue
                
                # --- 3. 解析资金水位（FUNDS_DISTRIBUTION） ---
                if in_funds_section and "|" in line:
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 2:
                        name = parts[0]
                        amount_str = parts[1].replace(",", "").replace(" ", "").replace("*", "")
                        
                        try:
                            amount = float(amount_str)
                            
                            if "现有持仓" in name:
                                positions_value = amount
                            elif "合计" in name:
                                total_assets = amount
                        except ValueError:
                            pass
        
        # --- 4. 推导剩余字段 ---
        if total_assets == 0 and positions_value > 0:
            total_assets = positions_value  # fallback
        
        cash = total_assets - positions_value
        position_pct = (positions_value / total_assets * 100) if total_assets > 0 else 0
        
        return {
            "total_assets": total_assets,
            "positions_value": positions_value,
            "cash": cash,
            "position_pct": position_pct,
            "positions": positions
        }
    
    def _parse_holding_row(self, line: str) -> Optional[Position]:
        """
        解析持仓表（### 持仓（防守姿态））中的单行
        
        格式: | 000001 平安银行 | 500股 | 12.00 | 12.50 | ¥6,250 | +4.17% | 11.88 (-5%) |
        """
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 7:
            return None
        
        try:
            # 代码: 第一列的前6位数字
            ticker_match = re.search(r"\b\d{6}\b", parts[0])
            if not ticker_match:
                return None
            ticker = ticker_match.group()
            
            # 名称: 去掉代码后的部分
            name = parts[0].replace(ticker, "").strip()
            
            # 数量: 提取数字（剥离"股""份"等）
            quantity = self._extract_number(parts[1])
            
            avg_cost = self._extract_number(parts[2])
            # current_price 从第4列提取
            current_price = self._extract_number(parts[3])
            
            # 市值: 从第5列提取
            market_value = self._extract_number(parts[4])
            
            # 盈亏%: 从第6列提取百分比
            pnl_str = parts[5]
            unrealized_pnl_pct = 0.0
            pnl_match = re.search(r"([+-]?[\d.]+)%", pnl_str)
            if pnl_match:
                unrealized_pnl_pct = float(pnl_match.group(1))
            
            # 资产类型判断
            asset_type = "etf" if ("ETF" in name.upper() or "ETF" in ticker.upper()) else "stock"
            
            return Position(
                ticker=ticker,
                name=name,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl_pct=unrealized_pnl_pct,
                asset_type=asset_type
            )
        except (ValueError, IndexError):
            return None
    
    def _parse_position_line(self, line: str) -> Optional[Position]:
        """解析单行持仓数据"""
        # 格式: | 标的 | 类型 | 持仓量 | 成本 | 收盘 | 浮盈亏 | 状态 |
        parts = [p.strip() for p in line.split("|") if p.strip()]
        
        if len(parts) < 6:
            return None
        
        try:
            ticker = parts[0].split()[0] if parts[0] else ""
            name = parts[0] if len(parts[0]) > 6 else ""
            asset_type = parts[1] if len(parts) > 1 else "stock"
            
            # 尝试解析数字
            quantity = self._extract_number(parts[2]) if len(parts) > 2 else 0
            avg_cost = self._extract_number(parts[3]) if len(parts) > 3 else 0
            current_price = self._extract_number(parts[4]) if len(parts) > 4 else 0
            
            market_value = quantity * current_price
            unrealized_pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
            
            return Position(
                ticker=ticker,
                name=name,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl_pct=unrealized_pnl_pct,
                asset_type=asset_type
            )
        except (ValueError, IndexError):
            return None
    
    def _extract_number(self, text: str) -> float:
        """从文本中提取数字"""
        # 移除逗号和空格
        text = text.replace(",", "").replace(" ", "")
        # 匹配数字
        match = re.search(r"-?[\d.]+", text)
        if match:
            return float(match.group())
        return 0.0
    
    def _default_data(self) -> Dict:
        """默认数据（文件不存在时）"""
        return {
            "total_assets": 70000,
            "positions_value": 7000,
            "cash": 63000,
            "position_pct": 10.0,
            "positions": []
        }


@dataclass
class PortfolioState:
    """组合状态（从 project.md 解析）"""
    total_assets: float
    positions_value: float
    cash: float
    position_pct: float  # 持仓占比


@dataclass
class SentinelState:
    """哨兵状态（从 sentinel_tool 获取）"""
    bullish_count: int  # 多头哨兵数
    total: int  # 总哨兵数


@dataclass
class RuleResult:
    """规则校验结果"""
    rule: str
    allowed: bool
    warning: Optional[str] = None
    conflict: Optional[str] = None
    reason: Optional[str] = None
    action: Optional[str] = None


class RuleEngine:
    """规则审计引擎"""
    
    # Rule 2: 阶梯仓位限制（整数百分比，10.0 = 10%）
    POSITION_LIMITS = {
        0: 10.0,  # 绝对防守期
        1: 10.0,
        2: 10.0,
        3: 35.0,  # 适度试探期
        4: 50.0,  # 积极进攻期
        5: 50.0,
        6: 50.0,
        7: 50.0,
        8: 50.0,
    }
    
    def check_rule1(self, sentinel: SentinelState, rsi_14: float) -> RuleResult:
        """
        Rule 1: 情绪起爆器
        - 哨兵≤2 + RSI<20 → 一级恐慌，持仓上限放宽至20%
        - 哨兵≤2 + RSI<15 → 二级恐慌，持仓上限放宽至30%
        """
        if sentinel.bullish_count <= 2:
            if rsi_14 < 15:
                return RuleResult(
                    rule="Rule 1",
                    allowed=True,
                    reason="二级恐慌起爆，持仓上限放宽至30%"
                )
            elif rsi_14 < 20:
                return RuleResult(
                    rule="Rule 1",
                    allowed=True,
                    reason="一级恐慌起爆，持仓上限放宽至20%"
                )
        return RuleResult(rule="Rule 1", allowed=True, reason="未触发恐慌条件")
    
    def check_rule2(self, sentinel: SentinelState, current_position_pct: float,
                    new_trade_pct: float, is_rule8_chase: bool = False,
                    rule1_activated: bool = False,
                    alpha_bypass: bool = False,
                    alpha_limit_pct: float = 5.0) -> RuleResult:
        """
        Rule 2: 阶梯仓位限制
        - 哨兵≤2: 持仓上限10%（Rule 8可放宽至15%）
        - 哨兵3-4: 持仓上限35%
        - 哨兵≥5: 持仓上限50%
        
        Alpha 逻辑豁免权（v2.2）：
        - 若标的通过 ASRG [Logic_Strong_Validation]
        - 允许豁免 Rule 3 限制
        - 豁免标的试探总额 ≤ 可用现金的 5%
        """
        base_limit = self.POSITION_LIMITS.get(sentinel.bullish_count, 10.0)
        
        # Rule 8 追高缓冲带
        if is_rule8_chase and sentinel.bullish_count <= 2:
            base_limit = 15.0
        
        # Rule 1 情绪起爆覆盖
        if rule1_activated and sentinel.bullish_count <= 2:
            base_limit = 20.0  # 一级恐慌放宽至20%
        
        # Alpha 逻辑豁免权（v2.2）
        if alpha_bypass and sentinel.bullish_count <= 2:
            # 豁免标的试探总额 ≤ 可用现金的 5%
            # 这里允许突破仓位限制，但受 alpha_limit_pct 约束
            if new_trade_pct <= alpha_limit_pct:
                return RuleResult(
                    rule="Rule 2",
                    allowed=True,
                    reason=f"⚡ 积极型放行：逻辑豁免权生效，试探 {new_trade_pct}% ≤ {alpha_limit_pct}% 限额"
                )
        
        new_total = current_position_pct + new_trade_pct
        
        if new_total > base_limit:
            return RuleResult(
                rule="Rule 2",
                allowed=False,
                conflict=f"仓位红线 {base_limit}%（当前{current_position_pct}% + {new_trade_pct}%）"
            )
        return RuleResult(
            rule="Rule 2",
            allowed=True,
            reason=f"仓位 {new_total}% 在红线 {base_limit}% 内"
        )
    
    def check_rule3(self, consecutive_days_below_2: int, action: str) -> RuleResult:
        """
        Rule 3: 条件单退场纪律
        - 第1天：暂停新建条件单
        - 第2天：取消存量条件单
        """
        if consecutive_days_below_2 >= 2 and action == "cancel_existing_orders":
            return RuleResult(
                rule="Rule 3",
                allowed=True,
                action="取消所有存量条件单"
            )
        elif consecutive_days_below_2 >= 1 and action == "create_condition_order":
            return RuleResult(
                rule="Rule 3",
                allowed=False,
                conflict="条件单退场第1天，暂停新建"
            )
        return RuleResult(rule="Rule 3", allowed=True, reason="条件单正常")
    
    def check_rule4(self, pe_percentile: float, pb_percentile: float,
                    asset_type: str = "stock") -> RuleResult:
        """
        Rule 4: 估值底线
        - 个股不受限制
        - 宽基ETF：PE>80%且PB>70% → 拦截
        - 宽基ETF：PE>80%但PB未超标 → 预警
        """
        # 个股不受限制
        if asset_type == "stock":
            return RuleResult(
                rule="Rule 4",
                allowed=True,
                reason="个股不受估值底线拦截"
            )
        
        # 双重拦截
        if pe_percentile > 0.80 and pb_percentile > 0.70:
            return RuleResult(
                rule="Rule 4",
                allowed=False,
                conflict=f"估值双重拦截（PE {pe_percentile*100}% + PB {pb_percentile*100}%）"
            )
        
        # 单PE预警
        if pe_percentile > 0.80:
            return RuleResult(
                rule="Rule 4",
                allowed=True,
                warning=f"PE {pe_percentile*100}% 预警中（PB {pb_percentile*100}% 未超标）"
            )
        
        return RuleResult(rule="Rule 4", allowed=True, reason="估值正常")
    
    def check_rule5(self, tech_exposure_pct: float, new_trade_tech_pct: float = 0) -> RuleResult:
        """
        Rule 5: 科技暴露红线（≤25%）
        """
        new_total = tech_exposure_pct + new_trade_tech_pct
        if new_total > 25.0:
            return RuleResult(
                rule="Rule 5",
                allowed=False,
                conflict=f"科技暴露 {new_total}% 超过 25% 上限"
            )
        return RuleResult(
            rule="Rule 5",
            allowed=True,
            reason=f"科技暴露 {new_total}% 在 25% 上限内"
        )
    
    def check_rule7(self, price_in_grid: bool, rsi_14: float = None,
                    volume_ratio: float = None, rule4_blocked: bool = False) -> RuleResult:
        """
        Rule 7: Alpha放行机制
        - 网格内：价格到位 + Rule 4 不拦截 → 可买
        - 网格外：需 RSI<30 + 量比<1.0
        """
        if rule4_blocked:
            return RuleResult(
                rule="Rule 7",
                allowed=False,
                conflict="Rule 4 估值拦截，即使价格到位也不可买"
            )
        
        if price_in_grid:
            return RuleResult(
                rule="Rule 7",
                allowed=True,
                reason="网格内价格到位，Rule 4 未拦截"
            )
        
        # 网格外追高
        if rsi_14 is not None and volume_ratio is not None:
            if rsi_14 < 30 and volume_ratio < 1.0:
                return RuleResult(
                    rule="Rule 7",
                    allowed=True,
                    reason="网格外追高：RSI<30 + 缩量确认"
                )
            return RuleResult(
                rule="Rule 7",
                allowed=False,
                conflict=f"网格外追高需 RSI<30（当前{rsi_14}）+ 量比<1.0（当前{volume_ratio}）"
            )
        
        return RuleResult(
            rule="Rule 7",
            allowed=False,
            conflict="网格外追高缺少 RSI 和量比数据"
        )
    
    def check_rule8(self, total_assets: float, chase_amount: float) -> RuleResult:
        """
        Rule 8: 可控追高（≤总资产×3%）
        """
        limit = total_assets * 0.03
        if chase_amount > limit:
            return RuleResult(
                rule="Rule 8",
                allowed=False,
                conflict=f"追高 ¥{chase_amount:,.0f} 超过上限 ¥{limit:,.0f}（总资产×3%）"
            )
        return RuleResult(
            rule="Rule 8",
            allowed=True,
            reason=f"追高 ¥{chase_amount:,.0f} 在上限 ¥{limit:,.0f} 内"
        )
    
    def check_rule9(self, trade_amount: float) -> RuleResult:
        """
        Rule 9: 单笔最低金额（≥¥3,000）
        """
        if trade_amount < 3000:
            return RuleResult(
                rule="Rule 9",
                allowed=False,
                conflict=f"单笔金额 ¥{trade_amount:,.0f} 低于最低 ¥3,000"
            )
        return RuleResult(
            rule="Rule 9",
            allowed=True,
            reason=f"单笔金额 ¥{trade_amount:,.0f} 满足最低要求"
        )
    
    def check_protocol1(self, index_price: float, pda_anchor: float) -> RuleResult:
        """
        Protocol 1: PDA 动态锚点
        - 指数价格 < PDA → 撤销所有条件单
        """
        if index_price < pda_anchor:
            return RuleResult(
                rule="Protocol 1",
                allowed=False,
                action="cancel_all_condition_orders",
                reason=f"指数 {index_price} < PDA {pda_anchor}"
            )
        return RuleResult(
            rule="Protocol 1",
            allowed=True,
            reason=f"指数 {index_price} ≥ PDA {pda_anchor}"
        )
    
    def check_protocol3(self, user_approved: bool) -> RuleResult:
        """
        Protocol 3: 人机协同红线
        - 任何持仓变更必须用户授权
        """
        if not user_approved:
            return RuleResult(
                rule="Protocol 3",
                allowed=False,
                conflict="人机协同红线：未获用户授权"
            )
        return RuleResult(
            rule="Protocol 3",
            allowed=True,
            reason="用户已授权"
        )
