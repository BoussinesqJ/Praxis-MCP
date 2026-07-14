"""约束检查器 — 交易执行前的纪律校验

5 项核心约束（使用 RuleMapping 统一规则定义）:
1. 禁入板块 (科创板688/588, 创业板300/159)
2. 投资工具限制 (禁止期权/杠杆)
3. 最小交易金额 (>5000元)
4. 现金底线 (交易后现金≥5%)
5. 单标的持仓上限 (≤30%)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from praxis.core.interfaces import ConstraintChecker
from praxis.core.models import PortfolioState, InvestorProfile, Portfolio, StrategyTemplate
from praxis.core.rule_mapping import RuleMapping
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class SimpleConstraintChecker(ConstraintChecker):
    """约束检查器 — 策略驱动"""

    def __init__(self, investor: InvestorProfile, portfolio: Portfolio,
                 strategy: StrategyTemplate | None = None):
        self._investor = investor
        self._portfolio = portfolio
        self._strategy = strategy

    def check(self, state: PortfolioState, action: str, ticker: str, **kwargs) -> list[dict]:
        """执行纪律校验 — 策略驱动模式（有策略时从 rules 读取参数化阈值）

        当 self._strategy 不为 None 时，从策略规则中读取参数：
        - execution_rules.min_transaction → min_amount_cny (默认3000)
        - risk_rules.cash_floor → min_pct (默认70%)
        - risk_rules.position_cap → max_single_pct (默认15%)
        - risk_rules.stop_loss → default_pct (默认-10%)
        - risk_rules.max_drawdown → pct (默认20%)
        - time_rules.offshore_fund_window → start/end (默认14:45-14:55)

        当 self._strategy 为 None 时，回退到硬编码默认值。
        """
        results: list[dict] = [
            self._check_banned_market(ticker),
            self._check_banned_instrument(ticker),
        ]

        if action in ("buy", "subscribe"):
            amount = float(kwargs.get("amount", 0))

            if self._strategy and self._strategy.rules:
                # ---- 策略驱动模式 ----
                min_tx = self._get_rule_param(
                    "execution_rules.min_transaction", "min_amount_cny", 5000.0)
                cash_pct = self._get_rule_param(
                    "risk_rules.cash_floor", "min_pct", 70.0)
                pos_cap = self._get_rule_param(
                    "risk_rules.position_cap", "max_single_pct", 15.0)

                results.append(self._check_min_transaction(
                    ticker, amount, min_amount=min_tx))
                results.append(self._check_cash_floor(
                    state, amount, reserve_pct=cash_pct / 100.0))
                results.append(self._check_position_cap(
                    state, ticker, amount, max_pct=pos_cap))
            else:
                # ---- 回退模式（硬编码默认值）----
                results.append(self._check_min_transaction(ticker, amount))
                results.append(self._check_cash_floor(state, amount))
                results.append(self._check_position_cap(state, ticker, amount))

        # 策略独有的纪律检查（仅在策略存在时执行）
        if self._strategy and self._strategy.rules:
            results.append(self._check_stop_loss(state, ticker))
            results.append(self._check_max_drawdown(state))
            results.append(self._check_trading_window())

        return results

    # ── 辅助方法 ──

    def _get_rule_param(self, rule_id: str, param_key: str, default: Any) -> Any:
        """从策略规则中提取参数，规则不存在或未启用时返回默认值"""
        if not self._strategy or not self._strategy.rules:
            return default
        for r in self._strategy.rules:
            if r.rule_id == rule_id and r.enabled:
                return r.params.get(param_key, default)
        return default

    # ── 硬性门禁（始终执行）──

    def _check_banned_market(self, ticker: str) -> dict:
        """检查禁入板块 — Rule 1/2"""
        is_star = ticker.startswith("688") or ticker.startswith("588")
        is_chinext = ticker.startswith("300") or ticker.startswith("159")

        if is_star:
            return {"rule": "Rule 1: 科创板禁入", "level": "hard_block",
                    "message": f"科创板标的 {ticker} 禁止交易", "passed": False}
        if is_chinext:
            return {"rule": "Rule 2: 创业板禁入", "level": "hard_block",
                    "message": f"创业板标的 {ticker} 禁止交易", "passed": False}

        return {"rule": "禁止板块检查", "level": "advisory",
                "message": "标的不在禁入板块", "passed": True}

    def _check_banned_instrument(self, ticker: str) -> dict:
        """检查投资工具限制 — Rule 4"""
        if "OPT" in ticker.upper() or ticker.startswith("CU") or ticker.startswith("IO"):
            return {"rule": "Rule 4: 工具限制", "level": "hard_block",
                    "message": f"期权/杠杆工具 {ticker} 禁止使用", "passed": False}
        return {"rule": "投资工具检查", "level": "advisory",
                "message": "工具类型合规", "passed": True}

    def _check_min_transaction(self, ticker: str, amount: float,
                                min_amount: float = 5000.0) -> dict:
        """检查最小交易金额 — Rule 15（min_amount 可由策略覆盖）"""
        if amount > 0 and amount < min_amount:
            return {"rule": "Rule 15: 最小交易金额", "level": "soft_warning",
                    "message": f"交易金额 {amount:.0f}元 低于最低 {min_amount:.0f}元", "passed": True}
        return {"rule": "最小交易金额检查", "level": "advisory",
                "message": "交易金额满足最低要求", "passed": True}

    def _check_cash_floor(self, state: PortfolioState, amount: float,
                           reserve_pct: float = 0.05) -> dict:
        """检查现金底线 — Rule 18（reserve_pct 可由策略覆盖，如 grid_value 设 0.70）"""
        if state.total_assets <= 0:
            return {"rule": "Rule 18: 现金底线", "level": "advisory",
                    "message": "无法判定总资产，跳过后备基金校验", "passed": True}

        cash_after = state.cash.total_cash - amount
        min_reserve = state.total_assets * reserve_pct

        if cash_after < min_reserve:
            return {"rule": "Rule 18: 现金底线", "level": "hard_block",
                    "message": f"交易后现金 {cash_after:.0f}元 < 最低后备 {min_reserve:.0f}元",
                    "passed": False}

        return {"rule": "现金底线检查", "level": "advisory",
                "message": "交易后现金满足后备要求", "passed": True}

    def _check_position_cap(self, state: PortfolioState, ticker: str, amount: float,
                             max_pct: float = 30.0) -> dict:
        """检查单标的持仓上限 — Rule 17（max_pct 可由策略覆盖，如 grid_value 设 15%）"""
        if state.total_assets <= 0:
            return {"rule": "Rule 17: 持仓上限", "level": "advisory",
                    "message": "无法判定总资产", "passed": True}

        current_mv = 0.0
        for pos in state.positions:
            if pos.ticker == ticker:
                current_mv = pos.market_value
                break

        new_mv = current_mv + amount
        new_pct = new_mv / state.total_assets * 100

        if new_pct > max_pct:
            return {"rule": "Rule 17: 单标的仓位上限", "level": "hard_block",
                    "message": f"{ticker} 仓位将达 {new_pct:.1f}% > {max_pct}%",
                    "passed": False}

        return {"rule": "持仓上限检查", "level": "advisory",
                "message": f"{ticker} 仓位 {new_pct:.1f}% 在安全范围内", "passed": True}

    # ── 策略驱动纪律（仅在策略存在时执行）──

    def _check_trading_window(self) -> dict:
        """检查交易时间窗口 — time_rules.offshore_fund_window（advisory 级别）"""
        rule_id = "time_rules.offshore_fund_window"
        start_str = self._get_rule_param(rule_id, "start", "14:45")
        end_str = self._get_rule_param(rule_id, "end", "14:55")

        now = datetime.now()
        try:
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))
        except (ValueError, AttributeError):
            return {"rule": "Rule: 交易时间窗口", "level": "advisory",
                    "message": f"时间窗口参数解析失败 ({start_str}-{end_str})，跳过", "passed": True}

        now_minutes = now.hour * 60 + now.minute
        window_start = start_h * 60 + start_m
        window_end = end_h * 60 + end_m

        if window_start <= now_minutes <= window_end:
            return {"rule": "Rule: 交易时间窗口", "level": "advisory",
                    "message": f"当前时间 {now.strftime('%H:%M')} 在交易窗口 {start_str}-{end_str} 内",
                    "passed": True}
        return {"rule": "Rule: 交易时间窗口", "level": "advisory",
                "message": f"当前时间 {now.strftime('%H:%M')} 不在交易窗口 {start_str}-{end_str} 内",
                "passed": True}

    def _check_stop_loss(self, state: PortfolioState, ticker: str) -> dict:
        """检查止损 — risk_rules.stop_loss（检查目标标的未实现亏损是否超阈值）"""
        rule_id = "risk_rules.stop_loss"
        stop_pct = self._get_rule_param(rule_id, "default_pct", -10.0)

        for pos in state.positions:
            if pos.ticker == ticker and pos.avg_cost > 0 and pos.current_price > 0:
                unrealized_pct = (pos.current_price / pos.avg_cost - 1) * 100
                if unrealized_pct <= stop_pct:
                    return {"rule": "Rule: 止损检查", "level": "hard_block",
                            "message": f"{ticker} 浮亏 {unrealized_pct:.1f}% 触及止损线 {stop_pct}%",
                            "passed": False}
                break

        return {"rule": "止损检查", "level": "advisory",
                "message": "未触发止损线", "passed": True}

    def _check_max_drawdown(self, state: PortfolioState) -> dict:
        """检查最大回撤 — risk_rules.max_drawdown"""
        rule_id = "risk_rules.max_drawdown"
        max_dd_pct = self._get_rule_param(rule_id, "pct", 20.0)

        # total_return_pct 为负时表示回撤
        if state.total_return_pct < 0 and abs(state.total_return_pct) > max_dd_pct:
            return {"rule": "Rule: 最大回撤检查", "level": "hard_block",
                    "message": f"当前回撤 {abs(state.total_return_pct):.1f}% 超过上限 {max_dd_pct}%",
                    "passed": False}

        return {"rule": "最大回撤检查", "level": "advisory",
                "message": f"回撤在安全范围内（上限 {max_dd_pct}%）", "passed": True}
