"""PRAXIS 核心接口定义（抽象基类）

所有模块先定义接口，再实现具体类。
V1 实现具体类，V2+ 可替换为不同实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from praxis.core.models.investor import InvestorProfile
    from praxis.core.models.portfolio import Portfolio
    from praxis.core.models.strategy import StrategyTemplate
    from praxis.core.models.transaction import Transaction
    from praxis.core.models.decision import DecisionRecord
    from praxis.core.models.state import PortfolioState
    from praxis.core.models.audit import AuditEvent


class DataProvider(ABC):
    """数据源接口（行情/新闻/情绪/基本面）"""

    @abstractmethod
    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情
        返回: {ticker: {price, change, change_pct, volume, ...}}
        """
        ...

    @abstractmethod
    async def get_history_kline(self, ticker: str, period: str = "day", count: int = 60) -> list[dict]:
        """获取历史K线
        返回: [{date, open, high, low, close, volume}, ...]
        """
        ...

    @abstractmethod
    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值（场外基金）
        返回: {nav, nav_date, acc_nav, ...}
        """
        ...


class ConfigLoader(ABC):
    """配置加载器接口"""

    @abstractmethod
    def load_investor(self, investor_id: str) -> "InvestorProfile":
        """加载投资者画像"""
        ...

    @abstractmethod
    def load_portfolio(self, investor_id: str, portfolio_id: str) -> "Portfolio":
        """加载投资组合配置"""
        ...

    @abstractmethod
    def load_strategy(self, strategy_name: str) -> "StrategyTemplate":
        """加载策略模板"""
        ...

    @abstractmethod
    def load_asset_detail(self, investor_id: str, portfolio_id: str, ticker: str) -> dict:
        """加载单标的详情（含网格/止损/止盈）"""
        ...


class Ledger(ABC):
    """交易账本接口（append-only）"""

    @abstractmethod
    def append(self, tx: "Transaction") -> str:
        """追加交易记录，返回 tx_id
        幂等：如果 idempotency_key 已存在，返回已有 tx_id
        """
        ...

    @abstractmethod
    def list(self, ticker: str | None = None, limit: int = 100) -> list["Transaction"]:
        """查询交易记录"""
        ...

    @abstractmethod
    def get(self, tx_id: str) -> "Transaction | None":
        """获取单条交易记录"""
        ...

    @abstractmethod
    def exists(self, idempotency_key: str) -> bool:
        """检查幂等键是否已存在"""
        ...

    @abstractmethod
    def delete(self, tx_id: str) -> bool:
        """物理删除单条交易记录"""
        ...

    @abstractmethod
    def purge(self, tag: str | None = None) -> int:
        """清空交易记录（按标签或全部），返回删除数"""
        ...

    @abstractmethod
    def verify_integrity(self) -> tuple[bool, list[str]]:
        """验证账本数据的完整性，返回 (是否完整, 错误列表)"""
        ...


class StateBuilder(ABC):
    """状态重建器接口"""

    @abstractmethod
    async def rebuild(
        self,
        investor_id: str,
        portfolio_id: str,
        market_data: dict | None = None,
    ) -> "PortfolioState":
        """从 ledger + 行情 + config 重建状态
        如果 market_data 为 None，自动获取最新行情
        """
        ...

    @abstractmethod
    def validate(self, state: "PortfolioState") -> list[str]:
        """验证状态一致性，返回问题列表"""
        ...


class ConstraintChecker(ABC):
    """约束检查器接口"""

    @abstractmethod
    def check(self, state: "PortfolioState", action: str, ticker: str, **kwargs) -> list[dict]:
        """检查约束
        返回: [{rule, level, message, passed}, ...]
        level: "hard_block" | "soft_warning" | "advisory"
        """
        ...


class DecisionRecorder(ABC):
    """决策记录器接口"""

    @abstractmethod
    def create(self, record: "DecisionRecord") -> str:
        """创建决策记录，返回 decision_id"""
        ...

    @abstractmethod
    def get(self, decision_id: str) -> "DecisionRecord | None":
        """获取决策记录"""
        ...

    @abstractmethod
    def update_status(self, decision_id: str, status: str, **kwargs) -> bool:
        """更新决策状态"""
        ...

    @abstractmethod
    def list_pending(self, limit: int = 50) -> list["DecisionRecord"]:
        """列出待审批的决策"""
        ...

    @abstractmethod
    def link_transaction(self, decision_id: str, tx_id: str) -> bool:
        """关联决策与交易"""
        ...


class PerformanceCalculator(ABC):
    """绩效计算器接口"""

    @abstractmethod
    def calculate(
        self,
        investor_id: str,
        portfolio_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """计算绩效指标
        返回: {total_return, annualized_return, benchmark_return, excess_return,
               max_drawdown, volatility, sharpe_ratio, calmar_ratio, win_rate,
               profit_loss_ratio, turnover_rate, total_fee}
        """
        ...

    @abstractmethod
    def compare_versions(
        self, version_a: str, version_b: str, metric: str = "sharpe_ratio"
    ) -> dict:
        """策略版本对比"""
        ...


class AuditLogger(ABC):
    """审计日志接口"""

    @abstractmethod
    def log(self, event: "AuditEvent") -> str:
        """记录审计事件，返回 event_id"""
        ...

    @abstractmethod
    def query(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list["AuditEvent"]:
        """查询审计事件"""
        ...


class BenchmarkProvider(ABC):
    """基准指数数据源接口"""

    @abstractmethod
    async def get_daily_kline(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """获取日K线数据
        返回: [{date, open, high, low, close, volume}, ...]
        """
        ...

    @abstractmethod
    async def get_latest_price(self, index_code: str) -> dict:
        """获取最新价格
        返回: {price, change, change_pct, date}
        """
        ...

    @abstractmethod
    def get_supported_indices(self) -> list[dict]:
        """获取支持的指数列表
        返回: [{code, name, description}, ...]
        """
        ...
