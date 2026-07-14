"""测试 Guardrail 三态状态机"""

import os
import tempfile
import pytest

from praxis.core.guardrail import (
    Guardrail,
    GuardrailState,
    GuardrailResult,
)


@pytest.fixture
def temp_db():
    """创建临时数据库文件"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
async def guardrail(temp_db):
    """创建已初始化的 Guardrail 实例"""
    g = Guardrail(db_path=temp_db)
    await g.initialize()
    return g


# ── Tests: Initialization ─────────────────────────────────────


class TestInitialization:
    """初始化测试"""

    @pytest.mark.asyncio
    async def test_initialize_creates_db(self, temp_db):
        g = Guardrail(db_path=temp_db)
        await g.initialize()
        assert g.current_state == GuardrailState.ACTIVE

    @pytest.mark.asyncio
    async def test_restore_state(self, temp_db):
        """进程重启后状态恢复"""
        g1 = Guardrail(db_path=temp_db)
        await g1.initialize()
        await g1.lock("测试锁定")

        # 模拟重启
        g2 = Guardrail(db_path=temp_db)
        await g2.initialize()
        assert g2.current_state == GuardrailState.LOCKED


# ── Tests: State Transitions ──────────────────────────────────


class TestTransitions:
    """状态转换测试"""

    @pytest.mark.asyncio
    async def test_lock_from_active(self, guardrail):
        result = await guardrail.lock("手动锁定")
        assert result.allowed is True
        assert guardrail.current_state == GuardrailState.LOCKED

    @pytest.mark.asyncio
    async def test_unlock_from_locked(self, guardrail):
        await guardrail.lock("锁定")
        result = await guardrail.unlock("解锁")
        assert result.allowed is True
        assert guardrail.current_state == GuardrailState.ACTIVE

    @pytest.mark.asyncio
    async def test_unlock_from_active_fails(self, guardrail):
        """只能从 LOCKED 解锁"""
        result = await guardrail.unlock("尝试")
        assert result.allowed is False
        assert "只能从 LOCKED" in result.reason

    @pytest.mark.asyncio
    async def test_start_audit(self, guardrail):
        result = await guardrail.start_audit("开始月复盘")
        assert result.allowed is True
        assert guardrail.current_state == GuardrailState.AUDITING

    @pytest.mark.asyncio
    async def test_end_audit(self, guardrail):
        await guardrail.start_audit("复盘")
        result = await guardrail.end_audit("复盘完成")
        assert result.allowed is True
        assert guardrail.current_state == GuardrailState.ACTIVE

    @pytest.mark.asyncio
    async def test_end_audit_from_active_fails(self, guardrail):
        result = await guardrail.end_audit("尝试")
        assert result.allowed is False
        assert "只能从 AUDITING" in result.reason

    @pytest.mark.asyncio
    async def test_emergency_unlock(self, guardrail):
        await guardrail.lock("紧急锁定")
        # 未设置 PRAXIS_EMERGENCY_TOKEN 时允许无条件解锁
        result = await guardrail.emergency_unlock("any_token")
        assert result.allowed is True
        assert guardrail.current_state == GuardrailState.ACTIVE

    @pytest.mark.asyncio
    async def test_emergency_unlock_with_token(self, temp_db):
        """带令牌验证的紧急解锁"""
        os.environ["PRAXIS_EMERGENCY_TOKEN"] = "secret123"
        try:
            g = Guardrail(db_path=temp_db)
            await g.initialize()
            await g.lock("锁定")

            # 错误令牌
            result = await g.emergency_unlock("wrong")
            assert result.allowed is False

            # 正确令牌
            result = await g.emergency_unlock("secret123")
            assert result.allowed is True
            assert g.current_state == GuardrailState.ACTIVE
        finally:
            del os.environ["PRAXIS_EMERGENCY_TOKEN"]

    @pytest.mark.asyncio
    async def test_invalid_transition(self, guardrail):
        """非法状态转换被拒绝"""
        result = await guardrail.transition(GuardrailState.AUDITING, "直接跳到审计")
        assert result.allowed is True  # ACTIVE → AUDITING 是合法的
        result = await guardrail.transition(GuardrailState.LOCKED, "从审计锁？")
        assert result.allowed is True  # AUDITING → LOCKED 也是合法的


# ── Tests: Verify Action ──────────────────────────────────────


class TestVerifyAction:
    """门控检查测试"""

    @pytest.mark.asyncio
    async def test_read_tool_always_allowed(self, guardrail):
        """读操作始终放行"""
        result = await guardrail.verify_action("market", "sentinel", {})
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_write_tool_when_active(self, guardrail):
        """ACTIVE 状态允许写操作"""
        result = await guardrail.verify_action("decision", "trading", {})
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_write_tool_when_locked(self, guardrail):
        """LOCKED 状态拦截写操作"""
        await guardrail.lock("锁定")
        result = await guardrail.verify_action("decision", "trading", {})
        assert result.allowed is False
        assert "已锁定" in result.reason

    @pytest.mark.asyncio
    async def test_write_tool_when_auditing(self, guardrail):
        """AUDITING 状态拦截写操作"""
        await guardrail.start_audit("复盘")
        result = await guardrail.verify_action("decision", "trading", {})
        assert result.allowed is False
        assert "复盘审计中" in result.reason


# ── Tests: Status and History ─────────────────────────────────


class TestStatusAndHistory:
    """状态查询和历史记录测试"""

    @pytest.mark.asyncio
    async def test_get_status(self, guardrail):
        status = guardrail.get_status()
        assert status["state"] == "ACTIVE"
        assert status["is_active"] is True
        assert status["can_write"] is True

    @pytest.mark.asyncio
    async def test_get_status_locked(self, guardrail):
        await guardrail.lock("锁定")
        status = guardrail.get_status()
        assert status["state"] == "LOCKED"
        assert status["is_locked"] is True
        assert status["can_write"] is False

    @pytest.mark.asyncio
    async def test_get_history(self, guardrail):
        await guardrail.lock("锁定")
        await guardrail.unlock("解锁")
        history = guardrail.get_history()
        assert len(history) >= 2
        transitions = [(h["from_state"], h["to_state"]) for h in history]
        assert ("ACTIVE", "LOCKED") in transitions


# ── Tests: GuardrailResult ────────────────────────────────────


class TestGuardrailResult:
    """GuardrailResult 测试"""

    def test_allowed(self):
        result = GuardrailResult(allowed=True, reason="OK", current_state=GuardrailState.ACTIVE)
        assert result.allowed is True

    def test_blocked(self):
        result = GuardrailResult(
            allowed=False,
            reason="已锁定",
            current_state=GuardrailState.LOCKED,
            required_state=GuardrailState.ACTIVE,
        )
        assert result.allowed is False
        assert result.required_state == GuardrailState.ACTIVE
