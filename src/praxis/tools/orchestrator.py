"""编排器工具 — orchestrator

工作流编排入口：支持预设工作流调用和自定义步骤编排。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from praxis.agents.base import Tool


class WorkflowInput(BaseModel):
    action: str = Field(..., description="操作: run/list")
    workflow_name: str = Field(default="", description="工作流名: decision_with_review/sentinel_scan/reconcile_cycle")
    ticker: str = Field(default="", description="标的代码（decision_with_review需要）")
    decision_action: str = Field(default="hold", description="决策动作: buy/sell/hold")
    confidence: float = Field(default=0.5, ge=0, le=1, description="置信度")
    reasoning: str = Field(default="", description="决策理由")
    investor: str = Field(default="demo", description="投资者ID")
    portfolio: str = Field(default="core", description="组合ID")


async def orchestrator(action: str, workflow_name: str = "", ticker: str = "",
                       decision_action: str = "hold", confidence: float = 0.5,
                       reasoning: str = "", investor: str = "demo",
                       portfolio: str = "core", _deps: dict | None = None) -> dict:
    """工作流编排入口"""
    if action == "list":
        return {"success": True, "data": {
            "workflows": [
                {"name": "decision_with_review", "description": "创建决策→执行→排期复盘", "params": "ticker/action/confidence/reasoning"},
                {"name": "sentinel_scan", "description": "哨兵扫描→估值检查→工作区发现", "params": "无"},
                {"name": "reconcile_cycle", "description": "对账→净值→绩效", "params": "investor/portfolio"},
            ]
        }}

    if action == "run" and workflow_name:
        # 需要访问 agents 字典
        agents = _deps.get("_agents", {}) if _deps else {}

        if workflow_name == "decision_with_review":
            from praxis.core.workflow import build_decision_with_review_workflow
            wf = build_decision_with_review_workflow(agents, ticker, decision_action, confidence, reasoning)
        elif workflow_name == "sentinel_scan":
            from praxis.core.workflow import build_sentinel_scan_workflow
            wf = build_sentinel_scan_workflow(agents)
        elif workflow_name == "reconcile_cycle":
            from praxis.core.workflow import build_reconcile_workflow
            wf = build_reconcile_workflow(agents, investor, portfolio)
        else:
            return {"success": False, "error": f"未知工作流: {workflow_name}"}

        result = await wf.execute()
        return {"success": result.success, "data": {
            "workflow": result.workflow_name,
            "steps_completed": result.steps_completed,
            "steps_failed": result.steps_failed,
            "steps": result.steps,
            "context": result.context,
        }}

    return {"success": False, "error": f"未知 action: {action}"}


def register(registry):
    registry.register(Tool(
        name="orchestrator",
        description="工作流编排：运行预设工作流（决策链/哨兵扫描/对账循环）",
        input_schema=WorkflowInput,
        handler=orchestrator,
        agent_name="admin",
        tier="advanced",
    ))
