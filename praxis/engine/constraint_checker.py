"""约束检查器"""
from __future__ import annotations

from praxis.core.interfaces import ConstraintChecker
from praxis.core.models.state import PortfolioState
from praxis.core.models.investor import InvestorProfile
from praxis.core.models.portfolio import Portfolio
from praxis.core.models.asset import AssetType
from praxis.core.models.strategy import StrategyTemplate


class SimpleConstraintChecker(ConstraintChecker):
    """约束检查器（策略驱动）"""

    def __init__(self, investor: InvestorProfile, portfolio: Portfolio, strategy: StrategyTemplate | None = None):
        self._investor = investor
        self._portfolio = portfolio
        self._strategy = strategy

    def check(self, state: PortfolioState, action: str, ticker: str, **kwargs) -> list[dict]:
        """检查约束

        Returns:
            list[dict]: [{rule, level, message, passed}, ...]
        """
        results = []

        # 1. 检查禁入板块
        market_result = self._check_banned_market(ticker)
        results.append(market_result)

        # 2. 检查禁入工具
        instrument_result = self._check_banned_instrument(ticker)
        results.append(instrument_result)

        # 3. 检查最小交易金额
        if action in ("buy", "subscribe"):
            amount = kwargs.get("amount", 0)
            min_amount_result = self._check_min_transaction(amount)
            results.append(min_amount_result)

        # 4. 检查现金底线
        if action in ("buy", "subscribe"):
            cash_result = self._check_cash_floor(state, kwargs.get("amount", 0))
            results.append(cash_result)

        # 5. 检查单标的持仓上限
        if action in ("buy", "subscribe"):
            position_result = self._check_position_cap(state, ticker, kwargs.get("amount", 0))
            results.append(position_result)

        return results

    def _check_banned_market(self, ticker: str) -> dict:
        """检查禁入板块（策略驱动）"""
        # 科创板: 688xxx, 588xxx
        # 创业板: 300xxx, 159xxx
        is_star = ticker.startswith("688") or ticker.startswith("588")
        is_chinext = ticker.startswith("300") or ticker.startswith("159")
        is_bse = ticker.startswith(("83", "87", "92", "43"))

        if not is_star and not is_chinext and not is_bse:
            return {
                "rule": "access_rules.blacklist_market",
                "level": "advisory",
                "message": f"标的 {ticker} 不在禁入板块",
                "passed": True,
            }

        # 从策略规则读取禁入板块配置
        banned_markets: list[str] = []
        etf_exempt = True
        if self._strategy:
            for rule in self._strategy.rules:
                if rule.rule == "access_rules.blacklist_market":
                    banned_markets = rule.params.get("markets", [])
                    etf_exempt = rule.params.get("etf_exempt", True)
                    break

        # Fallback: 策略未配置时从投资者约束读取
        if not banned_markets and self._investor.constraints.banned_markets:
            banned_markets = [m.id for m in self._investor.constraints.banned_markets]
            etf_exempt = self._investor.constraints.etf_exemption

        # ETF 豁免检查（精确前缀匹配）
        etf_prefixes = ("510", "512", "513", "515", "516", "588", "159", "160")
        is_etf = any(ticker.startswith(p) for p in etf_prefixes)
        if is_etf and etf_exempt:
            return {
                "rule": "access_rules.blacklist_market",
                "level": "advisory",
                "message": f"ETF {ticker} 受板块禁令豁免",
                "passed": True,
            }

        # 判断是否在禁入列表
        if is_star:
            market_id = "star_market"
        elif is_chinext:
            market_id = "chinext"
        else:
            market_id = "bse"
        banned = market_id in banned_markets

        market_label = "科创板" if is_star else ("创业板" if is_chinext else "北交所/新三板")
        return {
            "rule": "access_rules.blacklist_market",
            "level": "hard_block" if banned else "advisory",
            "message": f"{market_label}标的 {ticker}" + (" → hard_block 禁止买入" if banned else ""),
            "passed": not banned,
        }

    def _check_banned_instrument(self, ticker: str) -> dict:
        """检查禁入工具类型（策略驱动）"""
        banned_instruments: list[str] = []
        if self._strategy:
            for rule in self._strategy.rules:
                if rule.rule == "access_rules.blacklist_instrument":
                    banned_instruments = rule.params.get("instruments", [])
                    break

        if not banned_instruments:
            return {
                "rule": "access_rules.blacklist_instrument",
                "level": "advisory",
                "message": f"标的 {ticker} 无禁入工具规则",
                "passed": True,
            }

        # ETF 豁免：ETF 不受杠杆/做空禁令约束
        # 510xxx/512xxx/513xxx/515xxx/516xxx/588xxx = A股ETF
        # 159xxx = 创业板ETF / 160xxx = 混合型基金
        # 150xxx = 分级基金B（杠杆！不享受ETF豁免）
        etf_prefixes = ("510", "512", "513", "515", "516", "588", "159", "160")
        is_etf = any(ticker.startswith(p) for p in etf_prefixes)
        if is_etf:
            return {
                "rule": "access_rules.blacklist_instrument",
                "level": "advisory",
                "message": f"ETF {ticker} 不受工具禁令约束",
                "passed": True,
            }

        # 检测杠杆标的：B 级基金（150xxx）、分级基金 A/B
        is_leverage = ticker.startswith("150")
        # 检测期权：期权代码通常以特定前缀开头
        is_option = False  # 需要更精确的期权代码识别，目前无可靠前缀

        violations = []
        if "leverage" in banned_instruments and is_leverage:
            violations.append("杠杆工具")
        if "options" in banned_instruments and is_option:
            violations.append("期权工具")

        if violations:
            return {
                "rule": "access_rules.blacklist_instrument",
                "level": "hard_block",
                "message": f"标的 {ticker} → hard_block 禁入: {', '.join(violations)}",
                "passed": False,
            }

        return {
            "rule": "access_rules.blacklist_instrument",
            "level": "advisory",
            "message": f"标的 {ticker} 工具类型检查通过",
            "passed": True,
        }

    def _check_min_transaction(self, amount: float) -> dict:
        """检查最小交易金额"""
        min_amount = self._investor.execution.min_transaction_cny
        passed = amount >= min_amount
        return {
            "rule": "execution_rules.min_transaction",
            "level": "hard_block" if not passed else "advisory",
            "message": f"交易金额 ¥{amount:,.0f}" + (f" ≥ 最低 ¥{min_amount:,.0f}" if passed else f" < 最低 ¥{min_amount:,.0f}"),
            "passed": passed,
        }

    def _check_cash_floor(self, state: PortfolioState, amount: float) -> dict:
        """检查现金底线（策略驱动）"""
        cash_floor_pct = 0.40
        if self._strategy:
            for rule in self._strategy.rules:
                if rule.rule == "risk_rules.cash_floor":
                    cash_floor_pct = rule.params.get("min_pct", 40) / 100
                    break

        new_cash = state.cash.available_cash - amount
        new_ratio = new_cash / state.cash.total_assets if state.cash.total_assets > 0 else 0
        passed = new_ratio >= cash_floor_pct
        return {
            "rule": "risk_rules.cash_floor",
            "level": "hard_block" if not passed else "advisory",
            "message": f"交易后现金比例 {new_ratio:.1%}" + (f" ≥ 底线 {cash_floor_pct:.0%}" if passed else f" < 底线 {cash_floor_pct:.0%}"),
            "passed": passed,
        }

    def _check_position_cap(self, state: PortfolioState, ticker: str, amount: float) -> dict:
        """检查单标的持仓上限（策略驱动）"""
        position_cap_pct = 0.15
        if self._strategy:
            for rule in self._strategy.rules:
                if rule.rule == "risk_rules.position_cap":
                    position_cap_pct = rule.params.get("max_single_pct", 15) / 100
                    break

        # 从 state 中查找该标的当前持仓市值
        current_value = 0
        for pos in state.positions:
            if pos.ticker == ticker:
                current_value = pos.market_value
                break

        # 买入后的新市值
        new_value = current_value + amount
        total_assets = state.cash.total_assets if state.cash.total_assets > 0 else 1
        new_pct = new_value / total_assets
        passed = new_pct <= position_cap_pct

        return {
            "rule": "risk_rules.position_cap",
            "level": "hard_block" if not passed else "advisory",
            "message": f"标的 {ticker} 买入后持仓 {new_pct:.1%}" + (f" ≤ 上限 {position_cap_pct:.0%}" if passed else f" > 上限 {position_cap_pct:.0%}"),
            "passed": passed,
        }
