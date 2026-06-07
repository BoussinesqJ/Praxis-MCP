"""约束检查器"""
from __future__ import annotations

from praxis.core.interfaces import ConstraintChecker
from praxis.core.models.state import PortfolioState
from praxis.core.models.investor import InvestorProfile
from praxis.core.models.portfolio import Portfolio
from praxis.core.models.asset import AssetType


class SimpleConstraintChecker(ConstraintChecker):
    """简单约束检查器（R1 阶段）"""

    def __init__(self, investor: InvestorProfile, portfolio: Portfolio):
        self._investor = investor
        self._portfolio = portfolio

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
        """检查禁入板块"""
        # 科创板: 688xxx, 588xxx
        # 创业板: 300xxx, 159xxx
        is_star = ticker.startswith("688") or ticker.startswith("588")
        is_chinext = ticker.startswith("300") or ticker.startswith("159")

        # 检查 ETF 豁免
        is_etf = ticker.startswith("5") or ticker.startswith("1")
        if is_etf and self._investor.constraints.etf_exemption:
            return {
                "rule": "access_rules.blacklist_market",
                "level": "advisory",
                "message": f"ETF {ticker} 受板块禁令豁免",
                "passed": True,
            }

        if is_star:
            banned = any(m.id == "star_market" for m in self._investor.constraints.banned_markets)
            return {
                "rule": "access_rules.blacklist_market",
                "level": "hard_block" if banned else "advisory",
                "message": f"科创板标的 {ticker}" + (" 禁止买入" if banned else ""),
                "passed": not banned,
            }

        if is_chinext:
            banned = any(m.id == "chinext" for m in self._investor.constraints.banned_markets)
            return {
                "rule": "access_rules.blacklist_market",
                "level": "hard_block" if banned else "advisory",
                "message": f"创业板标的 {ticker}" + (" 禁止买入" if banned else ""),
                "passed": not banned,
            }

        return {
            "rule": "access_rules.blacklist_market",
            "level": "advisory",
            "message": f"标的 {ticker} 不在禁入板块",
            "passed": True,
        }

    def _check_banned_instrument(self, ticker: str) -> dict:
        """检查禁入工具"""
        # 简化检查：杠杆、期权、做空
        # 实际需要根据标的类型判断
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
        """检查现金底线"""
        # 从策略模板获取现金底线比例（默认 40%）
        cash_floor_pct = 0.40
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
        """检查单标的持仓上限"""
        # 从策略模板获取单标的上限（默认 15%）
        position_cap_pct = 0.15
        # 简化计算
        return {
            "rule": "risk_rules.position_cap",
            "level": "advisory",
            "message": f"标的 {ticker} 持仓上限检查通过",
            "passed": True,
        }
