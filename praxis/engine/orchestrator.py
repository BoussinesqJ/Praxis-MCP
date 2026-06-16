"""三团队编排引擎 (Orchestrator Engine)

根据 ASRG / Masters / Trading 的 SOP 流水线，
自动生成每个阶段的子Agent任务描述。

编排器不直接执行——它生成任务列表，由主Agent逐个调度子Agent执行。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MemberTask:
    """单个成员的子Agent任务"""
    agent_id: str          # 成员ID (如 "ethan")
    name: str              # 显示名 (如 "Ethan · 个股研究员")
    phase: int             # 阶段号 (1=并行, 2=串行, 3=决策, 4=风险)
    parallel: bool         # 是否与其他成员并行
    prompt: str            # 完整的子Agent Prompt
    tools: list[str]       # 可用工具列表
    needs_prev_phase: bool # 是否需要上一阶段的输出作为输入


@dataclass
class TeamPipeline:
    """一个团队的完整流水线"""
    team_name: str
    ticker: str
    name: str
    phases: list[list[MemberTask]] = field(default_factory=list)


# ── ASRG 团队定义 ─────────────────────────────────────────────────

ASRG_MEMBERS = {
    "ethan": {
        "name": "Ethan · 个股研究员",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data", "get_market_data"],
    },
    "james": {
        "name": "James · 估值定价师",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data", "get_valuation_percentile"],
    },
    "kevin": {
        "name": "Kevin · 资金行为分析师",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data", "mx-search"],
    },
    "frank": {
        "name": "Frank · 风险诊断师",
        "phase": 2, "parallel": False, "needs_prev_phase": True,
        "tools": ["check_constraints", "get_market_data"],
    },
}

ASRG_WORKFLOW = [
    {"phase": 1, "type": "parallel", "members": ["ethan", "james", "kevin"]},
    {"phase": 2, "type": "serial", "members": ["frank"]},
    {"phase": 3, "type": "compile", "members": ["gavin"]},
]


# ── Masters 团队定义 ──────────────────────────────────────────────

MASTERS_MEMBERS = {
    "oracle-of-omaha": {
        "name": "巴菲特 · 奥马哈先知",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data"],
    },
    "charlie-munger": {
        "name": "芒格 · 理性思维",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data"],
    },
    "magellan-captain": {
        "name": "彼得·林奇 · 麦哲伦舵手",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data"],
    },
    "the-big-short": {
        "name": "迈克尔·伯里 · 大空头",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data"],
    },
    "black-swan-prophet": {
        "name": "塔勒布 · 黑天鹅之父",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data"],
    },
    "macro-king": {
        "name": "德鲁肯米勒 · 宏观之王",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data", "get_market_data"],
    },
    "dhandho-master": {
        "name": "帕布莱 · Dhandho掌门",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data"],
    },
    "risk-manager": {
        "name": "风险管理师",
        "phase": 2, "parallel": False, "needs_prev_phase": True,
        "tools": [],
    },
    "portfolio-manager": {
        "name": "投资组合经理",
        "phase": 3, "parallel": False, "needs_prev_phase": True,
        "tools": ["check_constraints"],
    },
}

MASTERS_WORKFLOW = [
    {"phase": 1, "type": "parallel", "members": [
        "oracle-of-omaha", "charlie-munger", "magellan-captain",
        "the-big-short", "black-swan-prophet", "macro-king", "dhandho-master",
    ]},
    {"phase": 2, "type": "serial", "members": ["risk-manager"]},
    {"phase": 3, "type": "serial", "members": ["portfolio-manager"]},
    {"phase": 4, "type": "compile", "members": ["arthur"]},
]


# ── Trading 团队定义 ──────────────────────────────────────────────

TRADING_MEMBERS = {
    "market-analyst": {
        "name": "技术分析师",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data", "get_market_data"],
    },
    "fundamentals-analyst": {
        "name": "基本面分析师",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data"],
    },
    "news-analyst": {
        "name": "新闻分析师",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data", "mx-search"],
    },
    "sentiment-analyst": {
        "name": "情绪分析师",
        "phase": 1, "parallel": True, "needs_prev_phase": False,
        "tools": ["mx-data", "mx-search"],
    },
    "bull-researcher": {
        "name": "多头研究员",
        "phase": 2, "parallel": False, "needs_prev_phase": True,
        "tools": [],
    },
    "bear-researcher": {
        "name": "空头研究员",
        "phase": 2, "parallel": False, "needs_prev_phase": True,
        "tools": [],
    },
    "research-manager": {
        "name": "研究主管",
        "phase": 2, "parallel": False, "needs_prev_phase": True,
        "tools": [],
    },
    "trader": {
        "name": "交易员",
        "phase": 3, "parallel": False, "needs_prev_phase": True,
        "tools": ["check_constraints", "get_market_data"],
    },
    "aggressive-risk-analyst": {
        "name": "激进风险分析师",
        "phase": 4, "parallel": True, "needs_prev_phase": True,
        "tools": [],
    },
    "conservative-risk-analyst": {
        "name": "保守风险分析师",
        "phase": 4, "parallel": True, "needs_prev_phase": True,
        "tools": [],
    },
    "neutral-risk-analyst": {
        "name": "中性风险分析师",
        "phase": 4, "parallel": True, "needs_prev_phase": True,
        "tools": [],
    },
    "risk-manager": {
        "name": "风险主管",
        "phase": 4, "parallel": False, "needs_prev_phase": True,
        "tools": [],
    },
}

TRADING_WORKFLOW = [
    {"phase": 1, "type": "parallel", "members": [
        "market-analyst", "fundamentals-analyst", "news-analyst", "sentiment-analyst",
    ]},
    {"phase": 2, "type": "serial", "members": [
        "bull-researcher", "bear-researcher", "research-manager",
    ]},
    {"phase": 3, "type": "serial", "members": ["trader"]},
    {"phase": 4, "type": "parallel+serial", "members": [
        "aggressive-risk-analyst", "conservative-risk-analyst", "neutral-risk-analyst",
    ]},
    {"phase": 4.5, "type": "serial", "members": ["risk-manager"]},
    {"phase": 5, "type": "compile", "members": ["dominic"]},
]


# ── Prompt 模板 ──────────────────────────────────────────────────

MEMBER_PROMPT_TEMPLATE = """# 角色：{name}

{role_prompt}

---

## 本次分析任务

**标的**：{ticker} {stock_name}
**当前价**：{price}
**今日涨跌**：{change_pct}

---

## 可用数据

{market_data}

{financial_data}

{fund_flow}

---

## 前序分析（上一阶段成员的输出）

{prev_phase_output}

---

## 输出要求

按照你的角色提示词要求，输出结构化分析。
最后一行必须输出：[{signal_tag}] Bullish/Bearish/Neutral，信心X%，核心理由（一句话）
"""

GAVIN_COMPILE_TEMPLATE = """# 主理人 Gavin · 汇编报告

你是 ASRG 研究团队的主理人 Gavin。现在需要汇编各成员的分析产出，生成最终研究报告。

**标的**：{ticker} {stock_name}
**当前价**：{price}

---

## 各成员分析产出

{all_outputs}

---

## 汇编要求

1. 提取所有成员的信号（Bullish/Bearish/Neutral + 信心度）
2. 统计多空分布
3. 识别共识和分歧
4. 给出 ASRG 团队最终结论
5. 输出行动建议

格式参考 ASRG 输出规范：TL;DR → 核心结论卡片 → 行动清单 → 风险提示 → 免责声明
"""


class Orchestrator:
    """三团队编排器"""

    TEAM_REGISTRY = {
        "asrg": {"members": ASRG_MEMBERS, "workflow": ASRG_WORKFLOW},
        "masters": {"members": MASTERS_MEMBERS, "workflow": MASTERS_WORKFLOW},
        "trading": {"members": TRADING_MEMBERS, "workflow": TRADING_WORKFLOW},
    }

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._prompts_dir = self._workspace / "praxis" / "prompts"

    def get_team_members(self, team: str) -> dict:
        """获取团队成员列表"""
        return self.TEAM_REGISTRY.get(team, {}).get("members", {})

    def get_team_workflow(self, team: str) -> list:
        """获取团队 SOP 流程"""
        return self.TEAM_REGISTRY.get(team, {}).get("workflow", [])

    def generate_member_prompt(
        self,
        team: str,
        member_id: str,
        ticker: str,
        stock_name: str,
        price: float,
        change_pct: float,
        market_data: str = "",
        financial_data: str = "",
        fund_flow: str = "",
        prev_phase_output: str = "",
    ) -> str:
        """生成单个成员的子Agent Prompt"""
        members = self.get_team_members(team)
        member = members.get(member_id, {})
        name = member.get("name", member_id)

        # 信号标签
        signal_tag = f"{name}分析信号"

        # 角色 Prompt（从文件加载或使用默认）
        role_prompt = self._load_member_prompt(team, member_id)

        return MEMBER_PROMPT_TEMPLATE.format(
            name=name,
            role_prompt=role_prompt,
            ticker=ticker,
            stock_name=stock_name,
            price=price,
            change_pct=change_pct,
            market_data=market_data or "[数据待获取]",
            financial_data=financial_data or "[数据待获取]",
            fund_flow=fund_flow or "[数据待获取]",
            prev_phase_output=prev_phase_output or "[第一阶段，无前序输出]",
            signal_tag=signal_tag,
        )

    def generate_compile_prompt(
        self,
        team: str,
        ticker: str,
        stock_name: str,
        price: float,
        all_outputs: dict[str, str],
    ) -> str:
        """生成主理人汇编 Prompt"""
        outputs_text = ""
        for member_id, output in all_outputs.items():
            outputs_text += f"### {member_id}\n{output}\n\n---\n\n"

        template = GAVIN_COMPILE_TEMPLATE if team == "asrg" else GAVIN_COMPILE_TEMPLATE
        return template.format(
            ticker=ticker,
            stock_name=stock_name,
            price=price,
            all_outputs=outputs_text,
        )

    def get_phase_tasks(self, team: str, phase: int) -> list[dict]:
        """获取指定阶段的任务列表"""
        workflow = self.get_team_workflow(team)
        for step in workflow:
            if step["phase"] == phase:
                return step
        return {}

    def get_all_phases(self, team: str) -> list[dict]:
        """获取所有阶段"""
        return self.get_team_workflow(team)

    def _load_member_prompt(self, team: str, member_id: str) -> str:
        """加载成员的独立 Prompt"""
        prompt_file = self._prompts_dir / team / f"{member_id}.md"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")

        # 如果没有独立文件，返回通用模板
        members = self.get_team_members(team)
        member = members.get(member_id, {})
        return f"你是 {member.get('name', member_id)}，{team.upper()} 团队成员。请根据你的专业领域分析标的。"
