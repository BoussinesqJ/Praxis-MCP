"""策略模板模型"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RuleEntry(BaseModel):
    """规则条目"""
    rule: str
    params: dict = Field(default_factory=dict)


class TeamEmphasis(BaseModel):
    """AI 团队配置"""
    emphasis: list[str] = Field(default_factory=list)
    de_emphasis: list[str] = Field(default_factory=list)
    preferred_masters: list[str] = Field(default_factory=list)
    debate_focus: str = ""


class AITeamConfig(BaseModel):
    """AI 团队配置"""
    asrg: TeamEmphasis = Field(default_factory=TeamEmphasis)
    masters: TeamEmphasis = Field(default_factory=TeamEmphasis)
    trading: TeamEmphasis = Field(default_factory=TeamEmphasis)


class EvolutionDimension(BaseModel):
    """进化维度"""
    name: str
    desc: str
    metric: str
    healthy_range: list[float] | None = None
    threshold: float | None = None


class StrategyTemplate(BaseModel):
    """策略模板"""
    name: str
    description: str
    suitable_for: dict = Field(default_factory=dict)
    rules: list[RuleEntry] = Field(default_factory=list)
    ai_teams: AITeamConfig = Field(default_factory=AITeamConfig)
    performance_metrics: dict = Field(default_factory=dict)
    evolution_dimensions: list[EvolutionDimension] = Field(default_factory=list)
