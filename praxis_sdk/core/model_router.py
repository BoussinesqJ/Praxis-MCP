"""
Praxis v3.0 模型分级路由（Deep vs Quick Think）

解决"高射炮打蚊子"问题：用顶配模型做数据提取等脏活，浪费 API 成本。
通过 model_hint 标签自动路由到合适的模型。

映射策略（7 quick : 6 deep，预期降本 30-40%）：
- quick: Ethan / James / Kevin / Trading Phase 1 分析师 / Trading Phase 3 交易员
- deep:  Frank / Gavin / Masters 全员 / Trading Phase 2 辩论 / Phase 4 风险 / Dominic / LCD

使用方式：
    Skill 的 YAML frontmatter 中声明 model_hint: deep 或 model_hint: quick
    Reasonix Agent 在路由层根据声明自动选择底层调用的模型
"""

import os
from typing import Optional


# ─── 模型提示标签 ───────────────────────────────────────────

class ModelHint:
    """模型级别标签。"""
    DEEP = "deep"    # 深度思考：复杂推理、辩论、裁决
    QUICK = "quick"  # 快速思考：数据提取、格式转换、常规汇总


# ─── 子 Agent 模型映射表 ─────────────────────────────────────

# 三团队中每个子 Agent 的模型级别
AGENT_MODEL_MAP = {
    # ASRG 战术研究
    "asrg_ethan":      ModelHint.QUICK,   # 个股诊断 — 数据汇总
    "asrg_james":      ModelHint.QUICK,   # 估值判定 — 公式计算
    "asrg_kevin":      ModelHint.QUICK,   # 资金信号 — 数据解读
    "asrg_frank":      ModelHint.DEEP,    # 风险诊断 — 需要推理
    "asrg_gavin":      ModelHint.DEEP,    # 汇编输出 — 综合判断

    # Masters 大师圆桌
    "masters_buffett":     ModelHint.DEEP,  # 价值视角 — 哲学推理
    "masters_growth":      ModelHint.DEEP,  # 成长视角 — 哲学推理
    "masters_risk":        ModelHint.DEEP,  # 风控视角 — 哲学推理
    "masters_arthur":      ModelHint.DEEP,  # 汇编输出 — 综合判断

    # Trading 交易执行
    "trading_analysts":    ModelHint.QUICK,  # Phase 1 数据收集 — 情报提取
    "trading_debate":      ModelHint.DEEP,   # Phase 2 多空辩论 — 需要推理
    "trading_trader":      ModelHint.QUICK,  # Phase 3 交易员 — 执行方案
    "trading_risk":        ModelHint.DEEP,   # Phase 4 风险评估 — 风险权衡
    "trading_dominic":     ModelHint.DEEP,   # Dominic 最终裁决 — 最高决策

    # LCD 仲裁
    "lcd_arbitration":     ModelHint.DEEP,   # 规则优先级推理
}


# ─── 路由逻辑 ───────────────────────────────────────────────

def get_model_hint(agent_id: str) -> str:
    """根据 Agent ID 获取模型级别提示。

    Args:
        agent_id: 子 Agent 标识（如 "asrg_ethan"、"trading_dominic"）

    Returns:
        "deep" 或 "quick"
    """
    return AGENT_MODEL_MAP.get(agent_id, ModelHint.DEEP)  # 默认 deep（安全侧）


def get_model_for_agent(agent_id: str) -> Optional[str]:
    """获取指定 Agent 应使用的具体模型名称。

    优先级：
    1. 环境变量 PRAXIS_DEEP_MODEL / PRAXIS_QUICK_MODEL
    2. 返回 None（由 Reasonix 的 reasonix.toml 决定）
    """
    hint = get_model_hint(agent_id)

    if hint == ModelHint.DEEP:
        return os.environ.get("PRAXIS_DEEP_MODEL")
    else:
        return os.environ.get("PRAXIS_QUICK_MODEL")


def get_routing_summary() -> dict:
    """返回模型路由摘要（用于日志和调试）。"""
    deep_agents = [k for k, v in AGENT_MODEL_MAP.items() if v == ModelHint.DEEP]
    quick_agents = [k for k, v in AGENT_MODEL_MAP.items() if v == ModelHint.QUICK]
    return {
        "deep_model": os.environ.get("PRAXIS_DEEP_MODEL", "(not set)"),
        "quick_model": os.environ.get("PRAXIS_QUICK_MODEL", "(not set)"),
        "deep_agents": deep_agents,
        "quick_agents": quick_agents,
        "ratio": f"{len(quick_agents)} quick : {len(deep_agents)} deep",
    }
