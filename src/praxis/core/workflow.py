"""工作流编排引擎 — Agent 串行协作 + 条件分支 + 内置工作流

T5.1: 支持 Decision→Review→Admin 串行编排，步间上下文传递，失败处理。

Preset workflows:
    decision_with_review: 创建决策→执行交易→排期复盘→生成报表
    sentinel_scan: 哨兵扫描→约束检查→决策建议
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class FailureAction(str, Enum):
    SKIP = "skip"
    ABORT = "abort"
    RETRY = "retry"


@dataclass
class WorkflowStep:
    """工作流步骤"""
    name: str
    agent: str                          # Agent 名称
    tool: str                           # 工具名称
    params: dict = field(default_factory=dict)
    depends_on: Optional[str] = None    # 依赖的步骤名
    on_failure: FailureAction = FailureAction.ABORT
    condition: Optional[Callable] = None  # 条件函数(ctx) → bool
    status: StepStatus = StepStatus.PENDING
    result: dict | None = None
    error: str | None = None
    started_at: str = ""
    completed_at: str = ""


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    workflow_name: str
    success: bool
    steps_completed: int
    steps_failed: int
    steps: list[dict] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    error: str | None = None


class Workflow:
    """工作流编排引擎

    Usage:
        wf = Workflow("decision_with_review", agents)
        wf.add_step(WorkflowStep("create_decision", "decision", "decision", {...}))
        wf.add_step(WorkflowStep("execute_trade", "decision", "trading", {...}))
        result = await wf.execute()
    """

    def __init__(self, name: str, agents: dict[str, Any]):
        self.name = name
        self._agents = agents
        self._steps: list[WorkflowStep] = []
        self._context: dict = {}
        self._completed: set[str] = set()

    def add_step(self, step: WorkflowStep) -> "Workflow":
        self._steps.append(step)
        return self

    async def execute(self) -> WorkflowResult:
        """执行工作流"""
        completed = 0
        failed = 0
        steps_history = []

        for step in self._steps:
            # 检查依赖
            if step.depends_on and step.depends_on not in self._completed:
                step.status = StepStatus.SKIPPED
                step.error = f"依赖步骤 '{step.depends_on}' 未完成"
                steps_history.append(self._step_to_dict(step))
                continue

            # 检查条件
            if step.condition and not step.condition(self._context):
                step.status = StepStatus.SKIPPED
                steps_history.append(self._step_to_dict(step))
                continue

            # 执行步骤
            step.status = StepStatus.RUNNING
            step.started_at = datetime.now(timezone.utc).isoformat()

            agent = self._agents.get(step.agent)
            if agent is None:
                step.status = StepStatus.FAILED
                step.error = f"Agent '{step.agent}' 未找到"
                failed += 1
                steps_history.append(self._step_to_dict(step))
                if step.on_failure == FailureAction.ABORT:
                    break
                continue

            # 注入上下文数据
            params = {**step.params}
            if self._context:
                params["_context"] = self._context

            try:
                result = await agent.execute(step.tool, params)
                step.result = result.to_dict() if hasattr(result, 'to_dict') else {"data": result}
                step.status = StepStatus.COMPLETED

                # 传递上下文
                if result.success:
                    data = result.data if hasattr(result, 'data') else result
                    self._context[step.name] = data
                    if isinstance(data, dict):
                        self._context.update({f"{step.name}_{k}": v for k, v in data.items()})

                self._completed.add(step.name)
                completed += 1
                logger.info("workflow_step_completed", workflow=self.name, step=step.name)

            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                failed += 1
                logger.error("workflow_step_failed", workflow=self.name, step=step.name, error=str(e))

                if step.on_failure == FailureAction.ABORT:
                    steps_history.append(self._step_to_dict(step))
                    break
                elif step.on_failure == FailureAction.RETRY:
                    # 单次重试
                    try:
                        result = await agent.execute(step.tool, params)
                        step.result = result.to_dict() if hasattr(result, 'to_dict') else {"data": result}
                        step.status = StepStatus.COMPLETED
                        self._completed.add(step.name)
                        completed += 1
                        failed -= 1
                    except Exception:
                        pass

            step.completed_at = datetime.now(timezone.utc).isoformat()
            steps_history.append(self._step_to_dict(step))

        return WorkflowResult(
            workflow_name=self.name,
            success=failed == 0,
            steps_completed=completed,
            steps_failed=failed,
            steps=steps_history,
            context=self._context,
        )

    @staticmethod
    def _step_to_dict(step: WorkflowStep) -> dict:
        return {
            "name": step.name, "agent": step.agent, "tool": step.tool,
            "status": step.status.value, "error": step.error,
            "result": step.result, "started_at": step.started_at,
            "completed_at": step.completed_at,
        }


# ═══════════════════════════════════════════════════════════════
# 内置工作流
# ═══════════════════════════════════════════════════════════════


def build_decision_with_review_workflow(agents: dict, ticker: str, action: str,
                                        confidence: float, reasoning: str) -> Workflow:
    """Decision→Review 内置工作流：创建决策→执行→排期复盘"""
    wf = Workflow("decision_with_review", agents)

    wf.add_step(WorkflowStep(
        name="create_decision", agent="decision", tool="decision",
        params={"ticker": ticker, "action": action, "confidence": confidence, "reasoning": reasoning},
        on_failure=FailureAction.ABORT,
    ))
    wf.add_step(WorkflowStep(
        name="schedule_review", agent="review", tool="review",
        params={"action": "fill"},
        depends_on="create_decision",
        on_failure=FailureAction.SKIP,
    ))
    wf.add_step(WorkflowStep(
        name="agent_consensus", agent="review", tool="agent_tracking",
        params={"action": "consensus", "ticker": ticker},
        depends_on="create_decision",
        on_failure=FailureAction.SKIP,
    ))

    return wf


def build_sentinel_scan_workflow(agents: dict) -> Workflow:
    """哨兵扫描工作流：哨兵→估值→约束→建议"""
    wf = Workflow("sentinel_scan", agents)

    wf.add_step(WorkflowStep(
        name="scan_sentinel", agent="risk", tool="sentinel",
        params={"action": "scan"},
        on_failure=FailureAction.ABORT,
    ))
    wf.add_step(WorkflowStep(
        name="check_valuation", agent="risk", tool="valuation",
        params={"action": "all"},
        depends_on="scan_sentinel",
        on_failure=FailureAction.SKIP,
    ))
    wf.add_step(WorkflowStep(
        name="check_workspace", agent="admin", tool="discover_workspace",
        params={},
        on_failure=FailureAction.SKIP,
    ))

    return wf


def build_reconcile_workflow(agents: dict, investor: str, portfolio: str) -> Workflow:
    """对账工作流：对账→净值→绩效"""
    wf = Workflow("reconcile_cycle", agents)

    wf.add_step(WorkflowStep(
        name="run_reconcile", agent="admin", tool="reconcile",
        params={"investor": investor, "portfolio": portfolio},
        on_failure=FailureAction.ABORT,
    ))
    wf.add_step(WorkflowStep(
        name="get_nav", agent="admin", tool="nav",
        params={"action": "snapshot", "investor": investor, "portfolio": portfolio},
        depends_on="run_reconcile",
        on_failure=FailureAction.SKIP,
    ))
    wf.add_step(WorkflowStep(
        name="calc_performance", agent="admin", tool="performance",
        params={"investor": investor, "portfolio": portfolio},
        depends_on="run_reconcile",
        on_failure=FailureAction.SKIP,
    ))

    return wf
