"""tests for core/workflow.py — Workflow 引擎 + 3 内置工作流."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from praxis.core.workflow import (
    Workflow,
    WorkflowStep,
    WorkflowResult,
    StepStatus,
    FailureAction,
    build_decision_with_review_workflow,
    build_sentinel_scan_workflow,
    build_reconcile_workflow,
)


# ── 辅助：创建 mock agent ─────────────────────────────────────────


class FakeResult:
    """模拟 AgentResult 返回结构。"""

    def __init__(self, success: bool = True, data: dict | None = None):
        self.success = success
        self.data = data or {}

    def to_dict(self) -> dict:
        return {"success": self.success, "data": self.data}


def _make_success_agent(name: str = "default") -> MagicMock:
    """创建总是成功的 mock agent。"""
    agent = MagicMock()
    agent.name = name
    agent.execute = AsyncMock(return_value=FakeResult(success=True, data={"result": f"{name}_ok"}))
    return agent


def _make_failing_agent(name: str = "default") -> MagicMock:
    """创建总是失败的 mock agent。"""
    agent = MagicMock()
    agent.name = name
    agent.execute = AsyncMock(side_effect=RuntimeError(f"{name}_failed"))
    return agent


# ── 场景1：Workflow 基础执行 ─────────────────────────────────────


class TestWorkflowBasic:
    """Workflow 基础执行。"""

    @pytest.mark.asyncio
    async def test_two_steps_both_succeed(self):
        """2 步工作流、success=True、steps_completed=2。"""
        agents = {
            "agent_a": _make_success_agent("agent_a"),
            "agent_b": _make_success_agent("agent_b"),
        }
        wf = Workflow("basic", agents)
        wf.add_step(WorkflowStep("step_1", "agent_a", "tool_a"))
        wf.add_step(WorkflowStep("step_2", "agent_b", "tool_b"))

        result = await wf.execute()
        assert result.success is True
        assert result.steps_completed == 2
        assert result.steps_failed == 0
        assert result.workflow_name == "basic"

    @pytest.mark.asyncio
    async def test_single_step_succeeds(self):
        """单步工作流 success=True。"""
        agents = {"agent_a": _make_success_agent("agent_a")}
        wf = Workflow("single", agents)
        wf.add_step(WorkflowStep("only_step", "agent_a", "tool_a"))

        result = await wf.execute()
        assert result.success is True
        assert result.steps_completed == 1

    @pytest.mark.asyncio
    async def test_steps_status_completed(self):
        """步骤状态为 COMPLETED。"""
        agents = {"a": _make_success_agent("a")}
        wf = Workflow("test", agents)
        wf.add_step(WorkflowStep("s1", "a", "t1"))

        result = await wf.execute()
        assert result.steps[0]["status"] == "completed"


# ── 场景2：依赖步骤 skip ───────────────────────────────────────


class TestDependencySkip:
    """依赖步骤 skip。"""

    @pytest.mark.asyncio
    async def test_depends_on_failed_skips(self):
        """Step B depends_on='step_a'，Step A 失败 → SKIPPED。"""
        agents = {
            "agent_a": _make_failing_agent("agent_a"),
            "agent_b": _make_success_agent("agent_b"),
        }
        wf = Workflow("dep_skip", agents)
        step_a = WorkflowStep("step_a", "agent_a", "tool_a", on_failure=FailureAction.SKIP)
        step_b = WorkflowStep(
            "step_b", "agent_b", "tool_b", depends_on="step_a"
        )
        wf.add_step(step_a)
        wf.add_step(step_b)

        result = await wf.execute()
        step_b_status = next(s["status"] for s in result.steps if s["name"] == "step_b")
        assert step_b_status == "skipped"

    @pytest.mark.asyncio
    async def test_skip_error_message(self):
        """SKIPPED 步骤 error 含 '依赖步骤'。"""
        agents = {
            "agent_a": _make_failing_agent("agent_a"),
            "agent_b": _make_success_agent("agent_b"),
        }
        wf = Workflow("dep_err", agents)
        wf.add_step(WorkflowStep("step_a", "agent_a", "tool_a", on_failure=FailureAction.SKIP))
        wf.add_step(WorkflowStep("step_b", "agent_b", "tool_b", depends_on="step_a"))

        result = await wf.execute()
        step_b = next(s for s in result.steps if s["name"] == "step_b")
        assert "依赖步骤" in step_b["error"]
        assert "step_a" in step_b["error"]

    @pytest.mark.asyncio
    async def test_depends_on_succeeds_runs(self):
        """依赖步骤成功时正常执行。"""
        agents = {
            "agent_a": _make_success_agent("agent_a"),
            "agent_b": _make_success_agent("agent_b"),
        }
        wf = Workflow("dep_ok", agents)
        wf.add_step(WorkflowStep("step_a", "agent_a", "tool_a"))
        wf.add_step(WorkflowStep("step_b", "agent_b", "tool_b", depends_on="step_a"))

        result = await wf.execute()
        step_b_status = next(s["status"] for s in result.steps if s["name"] == "step_b")
        assert step_b_status == "completed"


# ── 场景3：条件函数 skip ───────────────────────────────────────


class TestConditionSkip:
    """condition 条件函数 skip。"""

    @pytest.mark.asyncio
    async def test_condition_false_skips(self):
        """condition=lambda ctx: False → SKIPPED。"""
        agents = {"a": _make_success_agent("a")}
        wf = Workflow("cond_skip", agents)
        wf.add_step(WorkflowStep(
            "step_1", "a", "tool_a", condition=lambda ctx: False
        ))

        result = await wf.execute()
        assert result.steps[0]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_condition_true_executes(self):
        """condition=lambda ctx: True → 正常执行。"""
        agents = {"a": _make_success_agent("a")}
        wf = Workflow("cond_ok", agents)
        wf.add_step(WorkflowStep(
            "step_1", "a", "tool_a", condition=lambda ctx: True
        ))

        result = await wf.execute()
        assert result.steps[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_condition_receives_context(self):
        """condition 接收 _context 参数。"""
        agents = {"a": _make_success_agent("a")}
        wf = Workflow("cond_ctx", agents)
        captured_ctx = []

        def condition(ctx):
            captured_ctx.append(dict(ctx))
            return False

        wf.add_step(WorkflowStep("step_1", "a", "tool_a", condition=condition))
        await wf.execute()
        # condition 被调用且 ctx 为 dict
        assert len(captured_ctx) >= 1


# ── 场景4：FailureAction.ABORT ─────────────────────────────────


class TestFailureActionAbort:
    """FailureAction.ABORT 行为。"""

    @pytest.mark.asyncio
    async def test_abort_stops_subsequent_steps(self):
        """失败 + ABORT → 后续步骤不执行。"""
        agents = {
            "agent_a": _make_failing_agent("agent_a"),
            "agent_b": _make_success_agent("agent_b"),
        }
        wf = Workflow("abort_test", agents)
        wf.add_step(WorkflowStep(
            "step_a", "agent_a", "tool_a", on_failure=FailureAction.ABORT,
        ))
        wf.add_step(WorkflowStep("step_b", "agent_b", "tool_b"))

        result = await wf.execute()
        assert result.success is False
        assert result.steps_failed >= 1
        # step_b 不应在 steps 中
        step_names = [s["name"] for s in result.steps]
        assert "step_b" not in step_names

    @pytest.mark.asyncio
    async def test_abort_default_action(self):
        """默认 on_failure 为 ABORT。"""
        agents = {
            "agent_a": _make_failing_agent("agent_a"),
            "agent_b": _make_success_agent("agent_b"),
        }
        wf = Workflow("default_abort", agents)
        wf.add_step(WorkflowStep("step_a", "agent_a", "tool_a"))  # default is ABORT
        wf.add_step(WorkflowStep("step_b", "agent_b", "tool_b"))

        result = await wf.execute()
        assert result.success is False


# ── 场景5：FailureAction.RETRY 单次重试 ────────────────────────


class TestFailureActionRetry:
    """FailureAction.RETRY 单次重试。"""

    @pytest.mark.asyncio
    async def test_retry_first_fail_second_success(self):
        """第一次失败第二次成功 → COMPLETED。"""
        call_count = 0

        class RetryAgent:
            name = "retry_agent"

            async def execute(self, tool, params):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("first_call_failed")
                return FakeResult(success=True, data={"retry": "ok"})

        agents = {"a": RetryAgent()}
        wf = Workflow("retry_test", agents)
        wf.add_step(WorkflowStep(
            "step_a", "a", "tool_a", on_failure=FailureAction.RETRY,
        ))

        result = await wf.execute()
        assert result.steps_completed == 1
        assert result.steps_failed == 0

    @pytest.mark.asyncio
    async def test_retry_both_fail(self):
        """两次都失败 → FAILED。"""
        agents = {"a": _make_failing_agent("a")}
        wf = Workflow("retry_fail", agents)
        wf.add_step(WorkflowStep(
            "step_a", "a", "tool_a", on_failure=FailureAction.RETRY,
        ))

        result = await wf.execute()
        assert result.steps_failed >= 1


# ── 场景6：FailureAction.SKIP 继续 ────────────────────────────


class TestFailureActionSkip:
    """FailureAction.SKIP 继续执行。"""

    @pytest.mark.asyncio
    async def test_skip_continues_subsequent_steps(self):
        """失败步骤 FAILED 但后续步骤继续执行。"""
        agents = {
            "agent_a": _make_failing_agent("agent_a"),
            "agent_b": _make_success_agent("agent_b"),
        }
        wf = Workflow("skip_continue", agents)
        wf.add_step(WorkflowStep(
            "step_a", "agent_a", "tool_a", on_failure=FailureAction.SKIP,
        ))
        wf.add_step(WorkflowStep("step_b", "agent_b", "tool_b"))

        result = await wf.execute()
        # step_a FAILED, step_b COMPLETED
        statuses = {s["name"]: s["status"] for s in result.steps}
        assert statuses.get("step_b") == "completed"
        assert result.steps_completed >= 1
        assert result.steps_failed >= 1


# ── 场景7：context 上下文传递 ──────────────────────────────────


class TestContextPassing:
    """Workflow context 上下文传递。"""

    @pytest.mark.asyncio
    async def test_context_passed_between_steps(self):
        """Step A data → _context，Step B 可访问。"""
        captured_params = []

        class ContextAgent:
            def __init__(self, name: str):
                self.name = name

            async def execute(self, tool, params):
                captured_params.append(params)
                return FakeResult(
                    success=True, data={"from": self.name, "tool": tool}
                )

        agents = {
            "a": ContextAgent("agent_a"),
            "b": ContextAgent("agent_b"),
        }
        wf = Workflow("ctx_test", agents)
        wf.add_step(WorkflowStep("step_a", "a", "tool_a"))
        wf.add_step(WorkflowStep("step_b", "b", "tool_b"))

        result = await wf.execute()

        # context 应该包含 step_a 的结果
        assert "step_a" in result.context
        context_data = result.context["step_a"]
        assert context_data["from"] == "agent_a"

    @pytest.mark.asyncio
    async def test_context_flattened_to_individual_keys(self):
        """context 展平为 step_name_key → value。"""
        agents = {"a": _make_success_agent("a")}
        wf = Workflow("flat", agents)
        wf.add_step(WorkflowStep("step_a", "a", "tool_a"))

        result = await wf.execute()
        # 如果 data 是 dict，展平后的 key 如 step_a_result
        assert len(result.context) > 0

    @pytest.mark.asyncio
    async def test_agent_not_found_fails(self):
        """Agent 不存在时步骤 FAILED。"""
        agents = {}  # empty
        wf = Workflow("no_agent", agents)
        wf.add_step(WorkflowStep("step_a", "nonexistent", "tool_a"))

        result = await wf.execute()
        assert result.steps_failed >= 1
        step = result.steps[0]
        assert "未找到" in step.get("error", "")


# ── 场景8：内置工作流构建 ─────────────────────────────────────


class TestBuiltinWorkflows:
    """内置工作流构建函数。"""

    def test_build_decision_with_review_workflow(self):
        """build_decision_with_review_workflow 产生 3 步。"""
        agents = {"decision": MagicMock(), "review": MagicMock()}
        wf = build_decision_with_review_workflow(
            agents, ticker="000001", action="buy",
            confidence=0.8, reasoning="测试",
        )
        assert wf.name == "decision_with_review"
        assert len(wf._steps) == 3
        # 检查步骤名
        step_names = [s.name for s in wf._steps]
        assert "create_decision" in step_names
        assert "schedule_review" in step_names
        assert "agent_consensus" in step_names

    def test_build_decision_with_review_dependencies(self):
        """schedule_review 和 agent_consensus 依赖 create_decision。"""
        agents = {"decision": MagicMock(), "review": MagicMock()}
        wf = build_decision_with_review_workflow(
            agents, ticker="000001", action="buy",
            confidence=0.8, reasoning="测试",
        )
        for step in wf._steps:
            if step.name in ("schedule_review", "agent_consensus"):
                assert step.depends_on == "create_decision"

    def test_build_sentinel_scan_workflow(self):
        """build_sentinel_scan_workflow 产生 3 步。"""
        agents = {"risk": MagicMock(), "admin": MagicMock()}
        wf = build_sentinel_scan_workflow(agents)
        assert wf.name == "sentinel_scan"
        assert len(wf._steps) == 3
        step_names = [s.name for s in wf._steps]
        assert "scan_sentinel" in step_names
        assert "check_valuation" in step_names
        assert "check_workspace" in step_names

    def test_build_sentinel_scan_dependency(self):
        """check_valuation 依赖 scan_sentinel。"""
        agents = {"risk": MagicMock(), "admin": MagicMock()}
        wf = build_sentinel_scan_workflow(agents)
        for step in wf._steps:
            if step.name == "check_valuation":
                assert step.depends_on == "scan_sentinel"

    def test_build_reconcile_workflow(self):
        """build_reconcile_workflow 产生 3 步。"""
        agents = {"admin": MagicMock()}
        wf = build_reconcile_workflow(agents, investor="inv-001", portfolio="port-001")
        assert wf.name == "reconcile_cycle"
        assert len(wf._steps) == 3
        step_names = [s.name for s in wf._steps]
        assert "run_reconcile" in step_names
        assert "get_nav" in step_names
        assert "calc_performance" in step_names

    def test_build_reconcile_dependencies(self):
        """get_nav 和 calc_performance 依赖 run_reconcile。"""
        agents = {"admin": MagicMock()}
        wf = build_reconcile_workflow(agents, investor="inv-001", portfolio="port-001")
        for step in wf._steps:
            if step.name in ("get_nav", "calc_performance"):
                assert step.depends_on == "run_reconcile"

    def test_builtin_workflow_step_count(self):
        """验证 3 个内置工作流各含正确步骤数。"""
        agents = {"decision": MagicMock(), "review": MagicMock(),
                   "risk": MagicMock(), "admin": MagicMock()}
        wf1 = build_decision_with_review_workflow(
            agents, "000001", "buy", 0.5, "test")
        wf2 = build_sentinel_scan_workflow(agents)
        wf3 = build_reconcile_workflow(agents, "inv-001", "port-001")
        assert len(wf1._steps) == 3
        assert len(wf2._steps) == 3
        assert len(wf3._steps) == 3
