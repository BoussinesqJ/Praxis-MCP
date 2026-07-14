"""规则编号映射表 — T0.1 三套编号双向映射

建立 28 条规则的文档层/代码层/模型层三套编号的统一映射。

文档层: "Rule 1" — 面向用户/LLM 的描述编号
代码层: "risk.cash_floor" — 代码中的规则 ID
模型层: Pydantic RuleEntry — 策略模板中的规则引用

Usage:
    from praxis.core.rule_mapping import RuleMapping

    # 正向解析
    RuleMapping.resolve("Rule 1")  # → {id, name, level, description}
    RuleMapping.resolve("risk.cash_floor")  # → {id, name, level, description}

    # 批量解析
    RuleMapping.resolve_many(["risk.cash_floor", "risk.trading_window"])
    # → {代码层ID: 规则详情}

    # 按文档层编号获取
    RuleMapping.get_by_doc_id(1)  # → Rule 1 详情

    # 按级别过滤
    RuleMapping.by_level("hard_block")  # → 所有硬拦截规则

    # 验证规则是否存在
    RuleMapping.exists("Rule 1")  # → True
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RuleDef:
    """单条规则定义"""
    rule_id: str              # 代码层 ID (e.g. "risk.cash_floor")
    doc_id: int               # 文档层编号 (e.g. 1)
    name: str                 # 规则名称
    level: str                # hard_block / soft_warning / advisory
    description: str          # 规则描述
    category: str = ""        # 分类: risk/position/timing/process/ai
    params: dict = field(default_factory=dict)  # 可配置参数


class RuleMapping:
    """28 条规则的三套编号双向映射"""

    RULES: list[RuleDef] = [
        # ── 板块禁入 (hard_block) ──
        RuleDef(doc_id=1,  rule_id="risk.banned_market_star",
                name="科创板禁入", level="hard_block", category="risk",
                description="禁止交易科创板标的（688/588开头）"),
        RuleDef(doc_id=2,  rule_id="risk.banned_market_chinext",
                name="创业板禁入", level="hard_block", category="risk",
                description="禁止交易创业板标的（300/159开头）"),

        # ── 工具限制 (hard_block) ──
        RuleDef(doc_id=3,  rule_id="risk.banned_instrument_leverage",
                name="杠杆工具禁入", level="hard_block", category="risk",
                description="禁止使用期权/期货/融资融券等杠杆工具"),
        RuleDef(doc_id=4,  rule_id="risk.banned_instrument_derivative",
                name="衍生品禁入", level="hard_block", category="risk",
                description="禁止使用任何衍生品工具"),

        # ── 仓位控制 (hard_block) ──
        RuleDef(doc_id=5,  rule_id="position.single_cap",
                name="单标的上限", level="hard_block", category="position",
                description="单一标的持仓不超过总资产的30%",
                params={"max_pct": 30.0}),
        RuleDef(doc_id=6,  rule_id="position.sector_cap",
                name="板块上限", level="hard_block", category="position",
                description="单一板块持仓不超过总资产的50%",
                params={"max_pct": 50.0}),
        RuleDef(doc_id=7,  rule_id="position.total_cap",
                name="总仓位上限", level="soft_warning", category="position",
                description="总持仓不超过总资产的95%",
                params={"max_pct": 95.0}),

        # ── 现金管理 (hard_block) ──
        RuleDef(doc_id=8,  rule_id="risk.cash_floor",
                name="现金底线", level="hard_block", category="risk",
                description="交易后现金不低于总资产的5%",
                params={"min_pct": 5.0}),
        RuleDef(doc_id=9,  rule_id="risk.min_cash_reserve",
                name="最低备用金", level="soft_warning", category="risk",
                description="始终保持至少5000元备用现金",
                params={"min_amount": 5000.0}),

        # ── 交易时机 (hard_block) ──
        RuleDef(doc_id=10, rule_id="risk.trading_window",
                name="交易时间窗口", level="hard_block", category="timing",
                description="仅允许在14:45-14:55执行买入操作",
                params={"start": "14:45", "end": "14:55"}),
        RuleDef(doc_id=11, rule_id="risk.trading_day_only",
                name="仅交易日", level="hard_block", category="timing",
                description="仅允许在A股交易日执行操作"),

        # ── 止损纪律 (hard_block) ──
        RuleDef(doc_id=12, rule_id="risk.stop_loss",
                name="止损线", level="hard_block", category="risk",
                description="单笔亏损超10%必须止损",
                params={"max_loss_pct": 10.0}),
        RuleDef(doc_id=13, rule_id="risk.max_drawdown",
                name="最大回撤", level="hard_block", category="risk",
                description="总回撤超20%暂停所有买入操作",
                params={"max_dd_pct": 20.0}),

        # ── 交易数量 (soft_warning) ──
        RuleDef(doc_id=14, rule_id="risk.daily_trade_limit",
                name="日交易上限", level="soft_warning", category="timing",
                description="每日最多5笔交易",
                params={"max_trades": 5}),
        RuleDef(doc_id=15, rule_id="risk.min_transaction",
                name="最小交易金额", level="soft_warning", category="risk",
                description="单笔交易不低于5000元",
                params={"min_amount": 5000.0}),

        # ── 持仓管理 (soft_warning) ──
        RuleDef(doc_id=16, rule_id="position.max_holdings",
                name="持仓数量上限", level="soft_warning", category="position",
                description="同时持有不超过10个标的",
                params={"max_count": 10}),
        RuleDef(doc_id=17, rule_id="position.concentration",
                name="持仓集中度", level="advisory", category="position",
                description="前3大持仓不超过总资产的60%",
                params={"top3_max_pct": 60.0}),

        # ── 决策流程 (process) ──
        RuleDef(doc_id=18, rule_id="process.decision_required",
                name="决策必记录", level="hard_block", category="process",
                description="每笔交易必须关联决策记录"),
        RuleDef(doc_id=19, rule_id="process.review_5d",
                name="5日复盘", level="soft_warning", category="process",
                description="交易后5日必须完成复盘"),
        RuleDef(doc_id=20, rule_id="process.review_20d",
                name="20日复盘", level="soft_warning", category="process",
                description="交易后20日进行中期复盘"),
        RuleDef(doc_id=21, rule_id="process.review_60d",
                name="60日复盘", level="advisory", category="process",
                description="交易后60日进行深度复盘"),

        # ── AI团队 (process) ──
        RuleDef(doc_id=22, rule_id="process.multi_agent_consensus",
                name="多Agent共识", level="soft_warning", category="process",
                description="重大决策需至少2个AI Agent达成共识"),
        RuleDef(doc_id=23, rule_id="sentinel.rule23_trigger",
                name="情绪起爆器", level="advisory", category="ai",
                description="哨兵雷达连续2日bullish_count≥4触发情绪起爆器"),

        # ── 估值约束 (advisory) ──
        RuleDef(doc_id=24, rule_id="valuation.pe_floor",
                name="PE低估判定", level="advisory", category="risk",
                description="指数PE低于30%分位时判定为低估区域"),
        RuleDef(doc_id=25, rule_id="valuation.pe_ceiling",
                name="PE高估拦截", level="soft_warning", category="risk",
                description="指数PE高于80%分位时拦截买入操作"),

        # ── 哨兵雷达 ──
        RuleDef(doc_id=26, rule_id="sentinel.attack_defense",
                name="攻防仓位阶梯", level="advisory", category="ai",
                description="根据bullish_count动态调整仓位上限(10%/20%/30%/50%)"),

        # ── 策略管理 ──
        RuleDef(doc_id=27, rule_id="strategy.version_lock",
                name="策略版本锁定", level="advisory", category="process",
                description="策略模板变更需灰度审批"),
        RuleDef(doc_id=28, rule_id="strategy.evolution_cycle",
                name="策略进化周期", level="advisory", category="process",
                description="每季度评估一次策略进化维度"),
    ]

    # ── 双向索引（懒加载） ──
    _by_rule_id: dict[str, RuleDef] = {}
    _by_doc_id: dict[int, RuleDef] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_init(cls):
        if not cls._initialized:
            for rule in cls.RULES:
                cls._by_rule_id[rule.rule_id] = rule
                cls._by_doc_id[rule.doc_id] = rule
            cls._initialized = True

    @classmethod
    def resolve(cls, identifier: str | int) -> Optional[dict]:
        """解析规则标识符

        Args:
            identifier: 规则编号或ID
                - 整型: 文档层编号 (e.g. 1 → Rule 1)
                - 字符串"Rule N": 文档层编号 (e.g. "Rule 1")
                - 字符串其他: 代码层ID (e.g. "risk.cash_floor")

        Returns:
            规则详情字典，不存在时返回 None
        """
        cls._ensure_init()

        # 文档层编号
        if isinstance(identifier, int):
            rule = cls._by_doc_id.get(identifier)
            return cls._to_dict(rule) if rule else None

        # "Rule N" 格式
        if identifier.startswith("Rule "):
            try:
                doc_id = int(identifier.replace("Rule ", ""))
                rule = cls._by_doc_id.get(doc_id)
                return cls._to_dict(rule) if rule else None
            except ValueError:
                return None

        # 代码层 ID
        rule = cls._by_rule_id.get(identifier)
        return cls._to_dict(rule) if rule else None

    @classmethod
    def resolve_many(cls, identifiers: list[str]) -> dict[str, dict]:
        """批量解析规则

        Returns:
            {rule_id: rule_dict} — 代码层ID到规则详情的映射
        """
        result = {}
        for ident in identifiers:
            rule_info = cls.resolve(ident)
            if rule_info:
                result[rule_info["rule_id"]] = rule_info
        return result

    @classmethod
    def get_by_doc_id(cls, doc_id: int) -> Optional[dict]:
        """按文档层编号获取规则"""
        return cls.resolve(doc_id)

    @classmethod
    def by_level(cls, level: str) -> list[dict]:
        """按级别过滤规则"""
        cls._ensure_init()
        return [cls._to_dict(r) for r in cls.RULES if r.level == level]

    @classmethod
    def by_category(cls, category: str) -> list[dict]:
        """按分类过滤规则"""
        cls._ensure_init()
        return [cls._to_dict(r) for r in cls.RULES if r.category == category]

    @classmethod
    def list_all(cls) -> list[dict]:
        """列出全部规则"""
        cls._ensure_init()
        return [cls._to_dict(r) for r in cls.RULES]

    @classmethod
    def exists(cls, identifier: str | int) -> bool:
        """检查规则是否存在"""
        return cls.resolve(identifier) is not None

    @classmethod
    def count(cls) -> int:
        return len(cls.RULES)

    @classmethod
    def get_hard_blocks(cls) -> list[str]:
        """获取所有 hard_block 规则的代码层 ID"""
        cls._ensure_init()
        return [r.rule_id for r in cls.RULES if r.level == "hard_block"]

    @staticmethod
    def _to_dict(rule: RuleDef) -> dict:
        return {
            "rule_id": rule.rule_id,
            "doc_id": rule.doc_id,
            "name": rule.name,
            "level": rule.level,
            "category": rule.category,
            "description": rule.description,
            "params": rule.params,
            "doc_ref": f"Rule {rule.doc_id}",
        }
