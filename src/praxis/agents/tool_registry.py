"""PRAXIS ToolRegistry — 插件式工具注册与发现

替代 mcp_server.py 中的硬编码 import 和 _TOOLS_TIER 字典。

核心方法:
    register(Tool)         — 注册单个工具
    get(name)              — 按名称获取工具
    list_by_agent(name)    — 按 Agent 列出工具
    list_all()             — 列出所有工具
    discover()             — 自动发现工具模块

特性:
    - 同名工具注册时报 ValueError
    - 延迟加载：工具首次调用时才初始化 handler
    - discover() 为"尽力而为"模式：失败的工具记录错误但继续
"""

from __future__ import annotations

import importlib
import os
import pkgutil
from pathlib import Path
from typing import Optional

from praxis.agents.base import Tool
from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """插件式工具注册中心

    Usage:
        registry = ToolRegistry()

        # 手动注册
        registry.register(Tool(name="sentinel", ...))

        # 自动发现
        count = await registry.discover()
        print(f"已注册 {count} 个工具")

        # 查询
        tool = registry.get("sentinel")
        tools = registry.list_by_agent("risk")
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._discovered_modules: set[str] = set()

    # ── 注册 ───────────────────────────────────────────────────

    def register(self, tool: Tool) -> None:
        """注册单个工具

        Args:
            tool: 工具描述符

        Raises:
            ValueError: 同名工具已注册
        """
        if tool.name in self._tools:
            existing = self._tools[tool.name]
            raise ValueError(
                f"工具名冲突: '{tool.name}' 已被 Agent '{existing.agent_name}' 注册。"
                f"新注册来自 Agent '{tool.agent_name}'。"
            )
        self._tools[tool.name] = tool
        logger.debug(
            "tool_registered",
            tool_name=tool.name,
            agent_name=tool.agent_name,
            tier=tool.tier,
            total_count=len(self._tools),
        )

    def register_many(self, tools: list[Tool]) -> int:
        """批量注册工具

        Args:
            tools: 工具描述符列表

        Returns:
            成功注册的数量
        """
        count = 0
        for tool in tools:
            try:
                self.register(tool)
                count += 1
            except ValueError as e:
                logger.warning("tool_register_conflict", error=str(e))
        return count

    # ── 查询 ───────────────────────────────────────────────────

    def get(self, name: str) -> Tool | None:
        """按名称获取工具"""
        return self._tools.get(name)

    def list_by_agent(self, agent_name: str) -> list[Tool]:
        """按 Agent 列出工具"""
        return [t for t in self._tools.values() if t.agent_name == agent_name]

    def list_by_tier(self, tier: str) -> list[Tool]:
        """按层级列出工具"""
        return [t for t in self._tools.values() if t.tier == tier]

    def list_all(self) -> list[Tool]:
        """列出所有已注册工具"""
        return list(self._tools.values())

    def get_tool_names(self) -> list[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())

    def get_agent_names(self) -> list[str]:
        """获取所有 Agent 名称"""
        return list(set(t.agent_name for t in self._tools.values()))

    def count(self) -> int:
        """已注册工具总数"""
        return len(self._tools)

    # ── 自动发现 ───────────────────────────────────────────────

    async def discover(self, tools_package: str = "praxis.tools") -> int:
        """自动发现工具模块

        扫描 tools_package 目录下的所有 .py 文件，
        调用每个模块的 register(registry) 函数（如果存在）。

        "尽力而为"模式：失败的模块记录错误但继续加载其他模块。

        Args:
            tools_package: 工具包路径（如 "praxis.tools"）

        Returns:
            成功发现的工具模块数量
        """
        try:
            package = importlib.import_module(tools_package)
        except ImportError as e:
            logger.error("tool_discovery_import_failed", package=tools_package, error=str(e))
            return 0

        package_path = Path(package.__file__).parent if package.__file__ else None
        if package_path is None:
            logger.error("tool_discovery_no_path", package=tools_package)
            return 0

        discovered = 0
        failed = 0
        skipped = 0

        for module_info in pkgutil.iter_modules([str(package_path)]):
            if module_info.name.startswith("_"):
                skipped += 1
                continue

            module_name = f"{tools_package}.{module_info.name}"

            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                logger.error(
                    "tool_module_import_failed",
                    module=module_name,
                    error=str(e),
                )
                failed += 1
                continue

            # 调用模块的 register(registry) 函数
            register_fn = getattr(module, "register", None)
            if register_fn is None:
                logger.debug("tool_module_no_register", module=module_name)
                skipped += 1
                continue

            try:
                before_count = self.count()
                register_fn(self)
                after_count = self.count()
                registered_in_module = after_count - before_count
                discovered += 1
                self._discovered_modules.add(module_name)
                logger.info(
                    "tool_module_discovered",
                    module=module_name,
                    tools_registered=registered_in_module,
                )
            except Exception as e:
                logger.error(
                    "tool_module_register_failed",
                    module=module_name,
                    error=str(e),
                )
                failed += 1

        summary = (
            f"工具发现完成: {discovered} 模块成功, "
            f"{failed} 失败, {skipped} 跳过, "
            f"总计注册 {self.count()} 个工具"
        )
        logger.info("tool_discovery_summary", summary=summary)

        return discovered

    # ── 冲突检测 ───────────────────────────────────────────────

    def detect_conflicts(self) -> list[dict]:
        """检测工具命名冲突"""
        seen: dict[str, list[str]] = {}
        for tool in self._tools.values():
            if tool.name not in seen:
                seen[tool.name] = []
            seen[tool.name].append(tool.agent_name)

        conflicts = [
            {"tool_name": name, "agents": agents}
            for name, agents in seen.items()
            if len(agents) > 1
        ]
        return conflicts

    # ── 导出 ───────────────────────────────────────────────────

    def export_manifest(self) -> dict:
        """导出完整的工具清单"""
        return {
            "total_tools": self.count(),
            "total_agents": len(self.get_agent_names()),
            "total_modules": len(self._discovered_modules),
            "agents": {
                agent: [
                    {
                        "name": t.name,
                        "description": t.description,
                        "tier": t.tier,
                        "is_readonly": t.is_readonly,
                    }
                    for t in self.list_by_agent(agent)
                ]
                for agent in sorted(self.get_agent_names())
            },
        }
