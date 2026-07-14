"""PRAXIS Engine 层 — 数据提供器引擎 + 交易执行 + 风控 + 决策 + 管理 + 复盘

导出:
    - 数据源: CachedDataProvider, ProviderRegistry
    - 交易执行: TradingCalendar, FeeModel, SlippageModel
    - 风控引擎: SentinelEngine, SimpleConstraintChecker, Valuation
    - 决策引擎: FileDecisionRecorder
    - 管理引擎: YamlConfigLoader, ReconciliationEngine, NavTracker
    - 复盘引擎: ReviewFiller, ConsensusEngine, AITracker
    - 绩效引擎: EnhancedPerformanceCalculator
"""

# T01: 数据源层
from praxis.engine.data import CachedDataProvider, ProviderRegistry

# T01: 交易执行
from praxis.engine.execution import TradingCalendar

# T02: 费用与滑点
from praxis.engine.execution.fee_model import FeeModel
from praxis.engine.execution.slippage_model import SlippageModel

# T02: 风控引擎
from praxis.engine.sentinel import SentinelEngine
from praxis.engine.valuation import get_valuation_percentile, check_valuation_for_all_indices
from praxis.engine.constraint_checker import SimpleConstraintChecker

# T02: 决策引擎
from praxis.engine.decision_recorder import FileDecisionRecorder

# T02: 管理引擎
from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.reconciliation import ReconciliationEngine

# T03: 复盘引擎 + 管理引擎
from praxis.engine.review_filler import ReviewFiller
from praxis.engine.nav_tracker import NavTracker
from praxis.engine.consensus import ConsensusEngine, AgentDecisionStore
from praxis.engine.ai_tracker import AITracker
from praxis.engine.performance import EnhancedPerformanceCalculator

# Phase 1 原有导出（保留向后兼容）
from praxis.engine.data_provider import CachedDataProvider as _LegacyCachedDataProvider

__all__ = [
    # T01
    "CachedDataProvider", "ProviderRegistry", "TradingCalendar",
    # T02
    "FeeModel", "SlippageModel",
    "SentinelEngine", "get_valuation_percentile", "check_valuation_for_all_indices",
    "SimpleConstraintChecker", "FileDecisionRecorder",
    "YamlConfigLoader", "ReconciliationEngine",
    # T03
    "ReviewFiller", "NavTracker", "ConsensusEngine", "AgentDecisionStore",
    "AITracker", "EnhancedPerformanceCalculator",
]
