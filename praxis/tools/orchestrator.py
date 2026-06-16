"""三团队编排 MCP 工具层

暴露 4 个工具：
  - run_asrg_team        ASRG 全流程（Gavin + 7人）
  - run_masters_team     Masters 全流程（Arthur + 21人）
  - run_trading_team     Trading 全流程（Dominic + 12人）
  - run_full_analysis    三团队联合研判
"""
from __future__ import annotations

from typing import Any


async def get_team_analysis_plan(
    team: str,
    ticker: str,
    stock_name: str = "",
    price: float = 0,
    change_pct: float = 0,
    workspace: str = ".",
) -> dict[str, Any]:
    """生成团队分析的完整任务计划

    Args:
        team: 团队名称 (asrg/masters/trading)
        ticker: 标的代码
        stock_name: 标的名称
        price: 当前价
        change_pct: 今日涨跌幅
        workspace: 工作区路径

    Returns:
        包含所有阶段任务描述的计划，主Agent按计划调度子Agent
    """
    from praxis.engine.orchestrator import Orchestrator

    orch = Orchestrator(workspace=workspace)
    phases = orch.get_all_phases(team)
    members = orch.get_team_members(team)

    if not phases:
        return {"success": False, "error": f"未知团队: {team}"}

    plan = {
        "success": True,
        "data": {
            "team": team,
            "ticker": ticker,
            "stock_name": stock_name,
            "price": price,
            "total_phases": len(phases),
            "total_members": len(members),
            "phases": [],
        },
    }

    for step in phases:
        phase_info = {
            "phase": step["phase"],
            "type": step["type"],
            "tasks": [],
        }
        for member_id in step.get("members", []):
            member = members.get(member_id, {"name": member_id})
            phase_info["tasks"].append({
                "agent_id": member_id,
                "name": member.get("name", member_id),
                "tools": member.get("tools", []),
                "needs_prev_phase": member.get("needs_prev_phase", False),
            })
        plan["data"]["phases"].append(phase_info)

    return plan


async def generate_member_prompt(
    team: str,
    member_id: str,
    ticker: str,
    stock_name: str = "",
    price: float = 0,
    change_pct: float = 0,
    market_data: str = "",
    financial_data: str = "",
    fund_flow: str = "",
    prev_phase_output: str = "",
    workspace: str = ".",
    model_hint: str = "deep",
) -> dict[str, Any]:
    """为指定成员生成完整的子Agent Prompt

    主Agent调用此工具获取单个成员的分析Prompt，然后用 task() 工具生成子Agent。

    Args:
        team: 团队名称
        member_id: 成员ID
        ticker: 标的代码
        stock_name: 标的名称
        price: 当前价
        change_pct: 涨跌幅
        market_data: 实时行情数据（JSON字符串）
        financial_data: 财务数据（JSON字符串）
        fund_flow: 资金流向数据（JSON字符串）
        prev_phase_output: 上一阶段的输出文本
        workspace: 工作区路径
        model_hint: 模型级别 "deep" 或 "quick"（v3.0 新增）

    Returns:
        完整的子Agent Prompt文本，可直接传给 task() 工具
    """
    from praxis.engine.orchestrator import Orchestrator
    from praxis_sdk.core.model_router import get_model_hint, get_model_for_agent, ModelHint

    # v3.0: 自动解析 model_hint（如果未显式指定，从映射表获取）
    agent_id = f"{team}_{member_id}"
    resolved_hint = model_hint if model_hint in ("deep", "quick") else get_model_hint(agent_id)
    suggested_model = get_model_for_agent(agent_id)

    orch = Orchestrator(workspace=workspace)
    prompt = orch.generate_member_prompt(
        team=team,
        member_id=member_id,
        ticker=ticker,
        stock_name=stock_name,
        price=price,
        change_pct=change_pct,
        market_data=market_data,
        financial_data=financial_data,
        fund_flow=fund_flow,
        prev_phase_output=prev_phase_output,
    )

    members = orch.get_team_members(team)
    member = members.get(member_id, {})

    return {
        "success": True,
        "data": {
            "agent_id": agent_id,
            "name": member.get("name", member_id),
            "phase": member.get("phase", 1),
            "parallel": member.get("parallel", False),
            "tools": member.get("tools", []),
            "prompt": prompt,
            "prompt_length": len(prompt),
            "model_hint": resolved_hint,
            "suggested_model": suggested_model,
        },
    }


async def generate_compile_prompt(
    team: str,
    ticker: str,
    stock_name: str,
    price: float,
    all_outputs: dict,
    workspace: str = ".",
) -> dict[str, Any]:
    """生成主理人汇编 Prompt

    Args:
        team: 团队名称
        ticker: 标的代码
        stock_name: 标的名称
        price: 当前价
        all_outputs: {member_id: analysis_output} 字典
        workspace: 工作区路径

    Returns:
        主理人的汇编 Prompt
    """
    from praxis.engine.orchestrator import Orchestrator

    orch = Orchestrator(workspace=workspace)
    prompt = orch.generate_compile_prompt(
        team=team,
        ticker=ticker,
        stock_name=stock_name,
        price=price,
        all_outputs=all_outputs,
    )

    return {
        "success": True,
        "data": {
            "team": team,
            "ticker": ticker,
            "prompt": prompt,
            "prompt_length": len(prompt),
            "inputs_count": len(all_outputs),
        },
    }
