"""
Praxis LCD Detector - 逻辑冲突检测器 (Logic Conflict Detector)
检测规则之间的冲突并提供仲裁建议

LCD 优先级：Rule 4 > Rule 2 > Rule 7 > Rule 8
仲裁策略：Masters 价值底线优先
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Conflict:
    """规则冲突"""
    rule: str
    message: str
    current_value: Optional[str] = None
    limit_value: Optional[str] = None


@dataclass
class LCDResult:
    """LCD 检测结果"""
    allowed: bool
    conflicts: List[Conflict]
    resolution: str  # "OK" | "LCD_MASTERS_ARBITRATION" | "LCD_REJECT"
    arbitration_advice: Optional[str] = None


class LCDDetector:
    """逻辑冲突检测器"""
    
    # 规则优先级（数值越大优先级越高）
    RULE_PRIORITY = {
        "Rule 1": 5,
        "Rule 2": 8,
        "Rule 3": 7,
        "Rule 4": 10,  # 最高优先级：估值底线
        "Rule 5": 6,
        "Rule 6": 4,
        "Rule 7": 3,
        "Rule 8": 2,
        "Rule 9": 1,
        "Protocol 1": 9,
        "Protocol 2": 2,
        "Protocol 3": 10,  # 最高优先级：人机协同
    }
    
    def check_trade_vs_rules(self, ticker: str, price: float, size: float,
                             sentinel_bullish: int, current_position_pct: float,
                             total_assets: float, pe_pct: float = None,
                             pb_pct: float = None, price_in_grid: bool = False,
                             rsi_14: float = None, volume_ratio: float = None,
                             asset_type: str = "stock",
                             in_strong_gravity: bool = False,
                             alpha_bypass: bool = False) -> LCDResult:
        """
        检测单笔交易建议是否违反当前规则。
        
        v2.2 新增参数：
        - in_strong_gravity: 标的是否处于强引力买入区
        - alpha_bypass: 是否通过 ASRG [Logic_Strong_Validation]
        
        Returns:
            LCDResult with allowed, conflicts, resolution
        """
        conflicts = []
        
        # Rule 4: 估值拦截（最高优先级）
        if pe_pct and pb_pct and asset_type != "stock":
            if pe_pct > 0.80 and pb_pct > 0.70:
                conflicts.append(Conflict(
                    rule="Rule 4",
                    message=f"估值双重拦截（PE {pe_pct*100}% + PB {pb_pct*100}%）",
                    current_value=f"PE {pe_pct*100}%",
                    limit_value="PE 80% + PB 70%"
                ))
        
        # Rule 2: 仓位红线（整数百分比）+ 非线性扩张（v2.2）
        position_limits = {0: 20.0, 1: 20.0, 2: 20.0, 3: 35.0, 4: 50.0, 5: 50.0, 6: 50.0, 7: 50.0, 8: 50.0}
        max_pct = position_limits.get(sentinel_bullish, 10.0)
        
        # 非线性扩张（v2.2）：强引力买入区 + 量比<0.8 → 仓位上限扩张至15%
        if in_strong_gravity and volume_ratio and volume_ratio < 0.8 and sentinel_bullish <= 2:
            max_pct = 15.0
        
        # Alpha 逻辑豁免权（v2.2）：允许突破仓位限制
        if alpha_bypass and sentinel_bullish <= 2:
            # 豁免标的试探总额 ≤ 可用现金的 5%
            alpha_limit = total_assets * 0.05
            if size <= alpha_limit:
                # 不添加 Rule 2 冲突，允许通过
                pass
            else:
                # 豁免但超限
                conflicts.append(Conflict(
                    rule="Rule 2",
                    message=f"⚡ 逻辑豁免权生效但超限：试探 ¥{size:,.0f} > ¥{alpha_limit:,.0f}（现金5%）",
                    current_value=f"¥{size:,.0f}",
                    limit_value=f"¥{alpha_limit:,.0f}"
                ))
        else:
            # 正常检查
            new_position_pct = current_position_pct + (size / total_assets * 100) if total_assets > 0 else current_position_pct
            if new_position_pct > max_pct:
                conflicts.append(Conflict(
                    rule="Rule 2",
                    message=f"🚨 警告：已达绝对防守期持仓上限 {max_pct}%，拦截买入建议。",
                    current_value=f"{new_position_pct:.1f}%",
                    limit_value=f"{max_pct}%"
                ))
        
        # Rule 7: 价格到位但有冲突
        if price_in_grid and conflicts:
            conflicts.append(Conflict(
                rule="Rule 7",
                message=f"网格内价格到位（{price}）",
                current_value=f"¥{price}",
                limit_value="网格买点"
            ))
        
        # Rule 8: 追高限制
        chase_limit = total_assets * 0.03
        if size > chase_limit:
            conflicts.append(Conflict(
                rule="Rule 8",
                message=f"追高 ¥{size:,.0f} 超过上限 ¥{chase_limit:,.0f}（总资产×3%）",
                current_value=f"¥{size:,.0f}",
                limit_value=f"¥{chase_limit:,.0f}"
            ))
        
        # 冲突仲裁
        if not conflicts:
            return LCDResult(allowed=True, conflicts=[], resolution="OK")
        
        # 检查是否有 Rule 4 拦截（最高优先级）
        rule4_conflict = [c for c in conflicts if c.rule == "Rule 4"]
        if rule4_conflict:
            return LCDResult(
                allowed=False,
                conflicts=conflicts,
                resolution="LCD_REJECT",
                arbitration_advice="Rule 4 估值底线拦截，无论其他规则如何放行都不可买"
            )
        
        # 检查 Rule 2 vs Rule 7 冲突
        rule2_conflict = [c for c in conflicts if c.rule == "Rule 2"]
        rule7_conflict = [c for c in conflicts if c.rule == "Rule 7"]
        if rule2_conflict and rule7_conflict:
            return LCDResult(
                allowed=False,
                conflicts=conflicts,
                resolution="LCD_MASTERS_ARBITRATION",
                arbitration_advice="Rule 2 仓位红线优先于 Rule 7 价格到位，建议等待仓位回落或哨兵回暖"
            )
        
        # 其他冲突：取最高优先级规则
        highest_priority = max(conflicts, key=lambda c: self.RULE_PRIORITY.get(c.rule, 0))
        return LCDResult(
            allowed=False,
            conflicts=conflicts,
            resolution="LCD_REJECT",
            arbitration_advice=f"{highest_priority.rule} 优先级最高，执行其限制"
        )
    
    def check_portfolio_vs_rules(self, portfolio_state: dict, sentinel_bullish: int) -> LCDResult:
        """
        检测整个组合是否违反当前规则。
        
        Args:
            portfolio_state: {"position_pct": float, "tech_exposure_pct": float, ...}
            sentinel_bullish: 多头哨兵数
        """
        conflicts = []
        
        # 检查仓位（整数百分比）
        position_limits = {0: 20.0, 1: 20.0, 2: 20.0, 3: 35.0, 4: 50.0, 5: 50.0, 6: 50.0, 7: 50.0, 8: 50.0}
        max_pct = position_limits.get(sentinel_bullish, 10.0)
        current_pct = portfolio_state.get("position_pct", 0)
        if current_pct > max_pct:
            conflicts.append(Conflict(
                rule="Rule 2",
                message=f"🚨 警告：持仓 {current_pct}% 已达绝对防守期上限 {max_pct}%"
            ))
        
        # 检查科技暴露
        tech_exposure = portfolio_state.get("tech_exposure_pct", 0)
        if tech_exposure > 25:
            conflicts.append(Conflict(
                rule="Rule 5",
                message=f"科技暴露 {tech_exposure}% 超过 25% 上限"
            ))
        
        if not conflicts:
            return LCDResult(allowed=True, conflicts=[], resolution="OK")
        
        return LCDResult(
            allowed=False,
            conflicts=conflicts,
            resolution="LCD_REJECT",
            arbitration_advice="组合层面违规，需调整持仓后再操作"
        )
    
    def consensus_check(self, asrg_output: dict, trading_output: dict) -> LCDResult:
        """
        检测 ASRG 和 Trading 团队结论是否一致。
        
        Args:
            asrg_output: {"logic_strong_validation": bool, "recommendation": str}
            trading_output: {"pda_valid": bool, "recommendation": str}
        """
        conflicts = []
        
        # ASRG 标注强验证但 Trading 不认可
        if asrg_output.get("logic_strong_validation") and not trading_output.get("pda_valid"):
            conflicts.append(Conflict(
                rule="ASRG vs Trading",
                message="ASRG 标注 Logic_Strong_Validation 但 Trading 未计算出有效 PDA"
            ))
        
        # 建议方向相反
        asrg_rec = asrg_output.get("recommendation", "").lower()
        trading_rec = trading_output.get("recommendation", "").lower()
        if ("buy" in asrg_rec and "sell" in trading_rec) or ("sell" in asrg_rec and "buy" in trading_rec):
            conflicts.append(Conflict(
                rule="ASRG vs Trading",
                message=f"建议方向相反：ASRG={asrg_rec}, Trading={trading_rec}"
            ))
        
        if not conflicts:
            return LCDResult(allowed=True, conflicts=[], resolution="OK")
        
        return LCDResult(
            allowed=False,
            conflicts=conflicts,
            resolution="LCD_MASTERS_ARBITRATION",
            arbitration_advice="ASRG 与 Trading 结论相左，启动逻辑对撞室，Masters 做最终裁决"
        )
