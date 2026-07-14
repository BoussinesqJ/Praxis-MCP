"""PRAXIS MCP Server — Agent 编排器 (瘦身版 ≤250行)

将 1272 行的 mcp_server.py 上帝文件重构为轻量编排器：
    - 不再有硬编码 import
    - 不再有 _TOOLS_TIER 字典
    - 不再有逐个工具的手写 async def

架构:
    ToolRegistry.discover() → 发现 28 个工具
    → 5 个 Agent 路由
    → Guardrail 门控（写操作）
    → FastMCP 动态注册

启动:
    PRAXIS_AGENT_MODE=true  → 新 Agent 模式（默认）
    PRAXIS_AGENT_MODE=false → 旧版 mcp_server_legacy 模式（保留兼容）
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time

from mcp.server.fastmcp import FastMCP

from praxis.agents.base import AgentDependencies
from praxis.agents.tool_registry import ToolRegistry
from praxis.agents.market import MarketAgent
from praxis.agents.risk import RiskAgent
from praxis.agents.decision import DecisionAgent
from praxis.agents.review import ReviewAgent
from praxis.agents.admin import AdminAgent
from praxis.core.guardrail import Guardrail
from praxis.core.feature_flags import FeatureFlag
from praxis.core.logging_config import get_logger

# ═══════════════════════════════════════════════════════════════════
# 日志 — 抑制第三方噪音
# ═══════════════════════════════════════════════════════════════════

for _noisy in ["httpx", "httpcore", "urllib3", "akshare", "ak"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

os.environ.setdefault("NO_PROXY", "*")

logger = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════
# 常量和配置
# ═══════════════════════════════════════════════════════════════════

WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", ".")
TOOL_TIMEOUT_SECONDS = int(os.environ.get("PRAXIS_TOOL_TIMEOUT", "30"))

# 全局实例
mcp = FastMCP("PRAXIS", json_response=True)
registry = ToolRegistry()
_agents: dict[str, object] = {}  # agent_name → Agent 实例
_guardrail: Guardrail | None = None


# ═══════════════════════════════════════════════════════════════════
# 初始化
# ═══════════════════════════════════════════════════════════════════


async def initialize() -> None:
    """初始化 Agent 系统：数据源 → Guardrail → Agent → 工具"""
    from praxis.engine.data_provider import CachedDataProvider

    logger.info("praxis_mcp_initializing", workspace=WORKSPACE)

    # 1. 数据提供器
    provider = CachedDataProvider(workspace=WORKSPACE)

    # 2. 引擎层 — Phase 2 基础设施
    from praxis.core.ledger import FileLedger
    from praxis.core.paths import get_ledger_path, get_decision_path
    from praxis.engine.config_loader import YamlConfigLoader
    from praxis.engine.sentinel import SentinelEngine
    from praxis.engine.reconciliation import ReconciliationEngine
    from praxis.engine.decision_recorder import FileDecisionRecorder
    from praxis.engine.review_filler import ReviewFiller
    from praxis.engine.nav_tracker import NavTracker
    from praxis.engine.performance import EnhancedPerformanceCalculator
    from praxis.core.paths import get_paths

    paths = get_paths(WORKSPACE)
    config_loader = YamlConfigLoader(WORKSPACE)

    ledger = FileLedger(get_ledger_path(WORKSPACE))
    decision_recorder = FileDecisionRecorder(get_decision_path(WORKSPACE, "core"))
    sentinel_engine = SentinelEngine(WORKSPACE, config_loader=config_loader)
    reconciliation_engine = ReconciliationEngine(config_loader, provider, ledger=ledger)
    review_filler = ReviewFiller(decision_recorder, ledger, provider)
    nav_tracker = NavTracker(paths["nav"] / "nav.jsonl", ledger, provider)
    performance_calculator = EnhancedPerformanceCalculator(ledger)

    # 2.5 Phase 4: 记忆存储
    memory_store = None
    if FeatureFlag.is_enabled("PRAXIS_MEMORY_ENABLED"):
        from praxis.core.memory_store import SimpleMemoryStore
        memory_store = SimpleMemoryStore(WORKSPACE)
        logger.info("memory_store_initialized", backend="SimpleMemoryStore")

    # 3. Guardrail（如果启用）
    global _guardrail
    if FeatureFlag.is_enabled("PRAXIS_GUARDRAIL_ENABLED"):
        db_path = os.path.join(WORKSPACE, "db", "praxis.db")
        _guardrail = Guardrail(db_path=db_path)
        await _guardrail.initialize()
        logger.info("guardrail_initialized", state=_guardrail.current_state.value)

    # 4. 依赖注入容器
    deps = AgentDependencies(
        data_provider=provider,
        workspace=WORKSPACE,
        guardrail=_guardrail,
        ledger=ledger,
        performance_calculator=performance_calculator,
        sentinel_engine=sentinel_engine,
        reconciliation_engine=reconciliation_engine,
        decision_recorder=decision_recorder,
        config_loader=config_loader,
        review_filler=review_filler,
        nav_tracker=nav_tracker,
        memory_store=memory_store,
    )

    # 4. 创建 Agent 实例
    _agents["market"] = MarketAgent(deps)
    _agents["risk"] = RiskAgent(deps)
    _agents["decision"] = DecisionAgent(deps)
    _agents["review"] = ReviewAgent(deps)
    _agents["admin"] = AdminAgent(deps)

    # 5. 自动发现工具（从 praxis.tools.registers 注册）
    await registry.discover()

    # 6. 从 Agent 补充工具注册
    for agent in _agents.values():
        for tool in agent.tools:
            try:
                registry.register(tool)
            except ValueError:
                pass  # 已在 registers.py 中注册过

    logger.info(
        "praxis_mcp_ready",
        agents=list(_agents.keys()),
        tools=registry.count(),
        guardrail_enabled=_guardrail is not None,
    )


# ═══════════════════════════════════════════════════════════════════
# MCP 工具动态注册
# ═══════════════════════════════════════════════════════════════════


def _create_tool_handler(agent_name: str, tool_name: str):
    """为 MCP 工具创建 handler 闭包

    闭包捕获 agent_name 和 tool_name，
    运行时路由到对应 Agent 的 execute() 方法。

    FastMCP 将所有参数序列化为单个 JSON 字符串 `params`，
    handler 负责反序列化后传递给 agent.execute()。
    """

    async def handler(params: str = "{}") -> dict:
        import json as _json

        start_time = time.time()

        # 反序列化 params JSON 字符串为字典
        if isinstance(params, str):
            try:
                kwargs = _json.loads(params)
            except _json.JSONDecodeError:
                kwargs = {"params": params}
        elif isinstance(params, dict):
            kwargs = params
        else:
            kwargs = {"params": params}

        logger.debug("tool_called", agent=agent_name, tool=tool_name, params=kwargs)

        agent = _agents.get(agent_name)
        if agent is None:
            return {"success": False, "error": f"Agent '{agent_name}' 未找到"}

        try:
            result = await asyncio.wait_for(
                agent.execute(tool_name, kwargs),
                timeout=TOOL_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            elapsed = (time.time() - start_time) * 1000
            logger.error(
                "tool_timeout",
                agent=agent_name,
                tool=tool_name,
                elapsed_ms=round(elapsed, 2),
            )
            return {
                "success": False,
                "error": f"工具调用超时 ({TOOL_TIMEOUT_SECONDS}s)",
                "_metadata": {
                    "agent_name": agent_name,
                    "tool_name": tool_name,
                    "execution_time_ms": round(elapsed, 2),
                },
            }

        return result.to_dict()

    return handler


def _register_all_tools() -> int:
    """遍历 ToolRegistry，将所有工具注册到 FastMCP"""
    count = 0
    for tool in registry.list_all():
        handler = _create_tool_handler(tool.agent_name, tool.name)
        # 设置 handler 的文档字符串（供 FastMCP 生成 tool description）
        handler.__doc__ = tool.description
        handler.__name__ = f"{tool.name}_tool"
        mcp.add_tool(handler)
        count += 1

    logger.info("mcp_tools_registered", count=count)
    return count


# ═══════════════════════════════════════════════════════════════════
# MCP Resource
# ═══════════════════════════════════════════════════════════════════


@mcp.resource("praxis://workspace/discovery")
def workspace_discovery_resource() -> dict:
    """Workspace 元数据（MCP Resource）"""
    return {
        "workspace": WORKSPACE,
        "agent_mode": FeatureFlag.is_enabled("PRAXIS_AGENT_MODE"),
        "guardrail_enabled": FeatureFlag.is_enabled("PRAXIS_GUARDRAIL_ENABLED"),
        "storage_backend": FeatureFlag.get_storage_backend(),
        "agents": list(_agents.keys()),
        "tools_count": registry.count(),
        "guardrail_status": _guardrail.get_status() if _guardrail else None,
    }


# ═══════════════════════════════════════════════════════════════════
# 启动入口
# ═══════════════════════════════════════════════════════════════════


def main():
    """启动 MCP Server — Agent 编排模式"""
    import contextlib

    # 检查 Feature Flag
    if not FeatureFlag.is_enabled("PRAXIS_AGENT_MODE"):
        sys.stderr.write(
            "⚠️  PRAXIS_AGENT_MODE=false，请使用旧版 mcp_server_legacy 模式\n"
        )
        sys.exit(1)

    # 初始化 Agent 系统
    with contextlib.redirect_stdout(sys.stderr):
        asyncio.run(initialize())

    # 注册所有工具到 FastMCP
    _register_all_tools()

    # 启动 MCP Server
    transport = os.environ.get("PRAXIS_TRANSPORT", "stdio").lower()

    if transport == "sse":
        host = os.environ.get("PRAXIS_HOST", "127.0.0.1")
        port = int(os.environ.get("PRAXIS_PORT", "8080"))
        sys.stderr.write(f"🚀 PRAXIS Agent MCP Server (SSE): http://{host}:{port}\n")
        sys.stderr.write(f"   Agents: {list(_agents.keys())}\n")
        sys.stderr.write(f"   Tools: {registry.count()}\n")
        sys.stderr.write(f"   Guardrail: {'Active' if _guardrail else 'Disabled'}\n")
        mcp.run(transport="sse", host=host, port=port)
    else:
        sys.stderr.write("🚀 PRAXIS Agent MCP Server v3.6 (stdio, params-fix)\n")
        sys.stderr.write(f"   Agents: {list(_agents.keys())}\n")
        sys.stderr.write(f"   Tools: {registry.count()}\n")
        mcp.run()


if __name__ == "__main__":
    main()
