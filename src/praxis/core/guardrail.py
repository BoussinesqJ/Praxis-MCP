"""PRAXIS Guardrail — 三态状态机纪律锁

从 praxis-mcp 项目移植的核心安全机制。

状态转换图:
    LOCKED ←──(紧急锁定)── 任意状态
    LOCKED ──(unlock)──→ ACTIVE
    ACTIVE ──(复盘触发)──→ AUDITING
    AUDITING ──(复盘完成)──→ ACTIVE

设计原则:
    1. 持久化到 SQLite — 进程重启后状态不丢失
    2. 状态变更全量审计日志
    3. 写操作前置拦截（DecisionAgent + AdminAgent 写操作）
    4. emergency_unlock 逃生机制
"""

from __future__ import annotations

import enum
import sqlite3
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class GuardrailState(str, enum.Enum):
    """Guardrail 状态枚举"""
    LOCKED = "LOCKED"       # 锁定：禁止所有写操作
    ACTIVE = "ACTIVE"       # 活跃：允许正常操作
    AUDITING = "AUDITING"   # 审计中：只读 + 复盘
    UNINITIALIZED = "UNINITIALIZED"  # 未初始化（首次启动）


# 合法状态转换映射
_VALID_TRANSITIONS: dict[GuardrailState, set[GuardrailState]] = {
    GuardrailState.UNINITIALIZED: {GuardrailState.LOCKED, GuardrailState.ACTIVE},
    GuardrailState.LOCKED:        {GuardrailState.ACTIVE},
    GuardrailState.ACTIVE:        {GuardrailState.LOCKED, GuardrailState.AUDITING},
    GuardrailState.AUDITING:      {GuardrailState.ACTIVE, GuardrailState.LOCKED},
}


# 写操作 Agent 清单（这些 Agent 的操作需要门控检查）
WRITE_AGENTS: set[str] = {"decision", "admin"}

# 写操作工具清单
WRITE_TOOLS: set[str] = {
    "trading",        # 交易执行
    "decision",       # 创建决策
    "portfolio",      # 组合修改（写部分）
    "nav",            # 净值记录
    "investor",       # 投资者初始化
}


@dataclass
class GuardrailResult:
    """Guardrail 验证结果"""
    allowed: bool
    reason: str = ""
    current_state: GuardrailState = GuardrailState.UNINITIALIZED
    required_state: GuardrailState | None = None


@dataclass
class Guardrail:
    """交易纪律硬拦截器

    Usage:
        guardrail = Guardrail(db_path="praxis.db")
        await guardrail.initialize()

        result = await guardrail.verify_action("decision", "trading", {...})
        if not result.allowed:
            raise GuardrailBlockedError(result.reason)
    """

    db_path: str
    current_state: GuardrailState = field(default=GuardrailState.UNINITIALIZED)
    _conn: sqlite3.Connection | None = field(default=None, repr=False)

    # ── 初始化 ───────────────────────────────────────────────

    async def initialize(self) -> None:
        """初始化 Guardrail：建表 + 恢复状态"""
        self._ensure_db()
        self._ensure_tables()
        self._restore_state()

    def _ensure_db(self) -> None:
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_tables(self) -> None:
        """创建 guardrail 相关表"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS guardrail_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state TEXT NOT NULL DEFAULT 'UNINITIALIZED',
                updated_at TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                updated_by TEXT NOT NULL DEFAULT 'system'
            );

            CREATE TABLE IF NOT EXISTS guardrail_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                updated_by TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_guardrail_history_ts
                ON guardrail_history(created_at);
        """)
        conn.commit()
        conn.close()

    def _restore_state(self) -> None:
        """从 DB 恢复上次状态（进程重启后不丢失）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT state FROM guardrail_state WHERE id = 1"
        ).fetchone()
        conn.close()

        if row:
            self.current_state = GuardrailState(row["state"])
        else:
            # 首次启动：默认 ACTIVE（由 feature flag 控制是否初始化）
            self.current_state = GuardrailState.ACTIVE
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO guardrail_state (id, state, updated_at, reason) "
                "VALUES (1, ?, ?, ?)",
                (self.current_state.value, datetime.now().isoformat(), "首次初始化"),
            )
            conn.commit()
            conn.close()

    # ── 状态转换 ─────────────────────────────────────────────

    async def transition(
        self, new_state: GuardrailState, reason: str = "", updated_by: str = "system"
    ) -> GuardrailResult:
        """状态转换（带前置条件校验）"""
        if new_state not in _VALID_TRANSITIONS.get(self.current_state, set()):
            return GuardrailResult(
                allowed=False,
                reason=f"非法状态转换: {self.current_state.value} → {new_state.value}",
                current_state=self.current_state,
            )

        old_state = self.current_state
        self.current_state = new_state

        # 持久化
        self._persist_state(new_state, reason, updated_by)
        self._record_history(old_state, new_state, reason, updated_by)

        return GuardrailResult(
            allowed=True,
            reason=f"状态已切换: {old_state.value} → {new_state.value}: {reason}",
            current_state=self.current_state,
        )

    def _persist_state(self, state: GuardrailState, reason: str, updated_by: str) -> None:
        """持久化状态到 SQLite"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO guardrail_state (id, state, updated_at, reason, updated_by) "
            "VALUES (1, ?, ?, ?, ?)",
            (state.value, datetime.now().isoformat(), reason, updated_by),
        )
        conn.commit()
        conn.close()

    def _record_history(
        self,
        from_state: GuardrailState,
        to_state: GuardrailState,
        reason: str,
        updated_by: str,
    ) -> None:
        """记录状态变更历史"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO guardrail_history (from_state, to_state, reason, updated_by) "
            "VALUES (?, ?, ?, ?)",
            (from_state.value, to_state.value, reason, updated_by),
        )
        conn.commit()
        conn.close()

    # ── 门控检查 ─────────────────────────────────────────────

    async def verify_action(
        self, agent_name: str, tool_name: str, params: dict | None = None
    ) -> GuardrailResult:
        """在执行写操作前进行门控检查

        Args:
            agent_name: 发起操作的 Agent 名称
            tool_name: 工具名称
            params: 工具参数（用于未来的细粒度检查）

        Returns:
            GuardrailResult: 验证结果
        """
        # 读操作无需检查
        if tool_name not in WRITE_TOOLS:
            return GuardrailResult(
                allowed=True,
                current_state=self.current_state,
            )

        # ACTIVE 状态允许所有操作
        if self.current_state == GuardrailState.ACTIVE:
            return GuardrailResult(
                allowed=True,
                current_state=self.current_state,
            )

        # AUDITING 状态禁止写操作
        if self.current_state == GuardrailState.AUDITING:
            return GuardrailResult(
                allowed=False,
                reason=f"复盘审计中，禁止写操作。Agent={agent_name}, Tool={tool_name}。"
                       f"请完成复盘后切换回 ACTIVE 状态。",
                current_state=self.current_state,
                required_state=GuardrailState.ACTIVE,
            )

        # LOCKED 状态禁止所有写操作
        if self.current_state == GuardrailState.LOCKED:
            return GuardrailResult(
                allowed=False,
                reason=f"系统已锁定，禁止写操作。Agent={agent_name}, Tool={tool_name}。"
                       f"如需解锁请使用 emergency_unlock。",
                current_state=self.current_state,
                required_state=GuardrailState.ACTIVE,
            )

        return GuardrailResult(
            allowed=False,
            reason=f"未知状态: {self.current_state.value}",
            current_state=self.current_state,
        )

    # ── 便捷操作 ─────────────────────────────────────────────

    async def lock(self, reason: str = "手动锁定") -> GuardrailResult:
        """锁定系统（紧急情况）"""
        return await self.transition(GuardrailState.LOCKED, reason)

    async def unlock(self, reason: str = "解锁") -> GuardrailResult:
        """解锁系统"""
        if self.current_state == GuardrailState.LOCKED:
            return await self.transition(GuardrailState.ACTIVE, reason)
        return GuardrailResult(
            allowed=False,
            reason=f"当前状态 {self.current_state.value}，只能从 LOCKED 解锁",
            current_state=self.current_state,
        )

    async def start_audit(self, reason: str = "开始复盘") -> GuardrailResult:
        """开始复盘审计"""
        if self.current_state == GuardrailState.ACTIVE:
            return await self.transition(GuardrailState.AUDITING, reason)
        return GuardrailResult(
            allowed=False,
            reason=f"当前状态 {self.current_state.value}，只能从 ACTIVE 开始审计",
            current_state=self.current_state,
        )

    async def end_audit(self, reason: str = "复盘完成") -> GuardrailResult:
        """结束复盘审计"""
        if self.current_state == GuardrailState.AUDITING:
            return await self.transition(GuardrailState.ACTIVE, reason)
        return GuardrailResult(
            allowed=False,
            reason=f"当前状态 {self.current_state.value}，只能从 AUDITING 结束审计",
            current_state=self.current_state,
        )

    async def emergency_unlock(self, auth_token: str) -> GuardrailResult:
        """紧急解锁（需要授权令牌）

        逃生机制：当系统因异常进入 LOCKED 状态时，
        提供绕过正常流程的紧急恢复通道。
        """
        # 简单的令牌验证（生产环境应使用更安全的机制）
        expected_token = os.environ.get("PRAXIS_EMERGENCY_TOKEN", "")
        if not expected_token:
            # 未配置紧急令牌时，允许无条件解锁
            pass
        elif auth_token != expected_token:
            return GuardrailResult(
                allowed=False,
                reason="紧急解锁令牌验证失败",
                current_state=self.current_state,
            )

        return await self.transition(
            GuardrailState.ACTIVE,
            reason="紧急解锁（emergency_unlock）",
            updated_by="emergency",
        )

    # ── 查询 ─────────────────────────────────────────────────

    def get_status(self) -> dict:
        """获取当前 Guardrail 状态"""
        return {
            "state": self.current_state.value,
            "is_locked": self.current_state == GuardrailState.LOCKED,
            "is_active": self.current_state == GuardrailState.ACTIVE,
            "is_auditing": self.current_state == GuardrailState.AUDITING,
            "can_write": self.current_state == GuardrailState.ACTIVE,
        }

    def get_history(self, limit: int = 20) -> list[dict]:
        """获取状态变更历史"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM guardrail_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ── 清理 ─────────────────────────────────────────────────

    async def auto_session(self) -> GuardrailResult | None:
        """根据交易时段自动切换状态"""
        try:
            from datetime import datetime
            now = datetime.now()
            from praxis.engine.execution.trading_calendar import TradingCalendar
            cal = TradingCalendar()
            if not cal.is_trading_day(now):
                if self.current_state == GuardrailState.ACTIVE:
                    return await self.transition(GuardrailState.LOCKED, "非交易日自动锁定")
            elif cal.is_trading_time(now):
                if self.current_state == GuardrailState.LOCKED:
                    return await self.transition(GuardrailState.ACTIVE, "交易时段自动激活")
            else:
                if self.current_state == GuardrailState.ACTIVE:
                    return await self.transition(GuardrailState.LOCKED, "非交易时段自动锁定")
        except Exception:
            pass
        return None

    async def close(self) -> None:
        """关闭 Guardrail"""
        pass  # SQLite 连接由每次操作独立管理，无需显式关闭
