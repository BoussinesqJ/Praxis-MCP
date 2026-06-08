"""数据源注册表 + 插件自动发现

职责：
- 注册内置数据源（东方财富/腾讯/AKShare/Baostock）
- 扫描 providers/ 目录发现用户自定义数据源
- 按优先级返回可用的数据源链
- 健康检查：连续失败 N 次临时标记为 unhealthy
"""
from __future__ import annotations

import importlib
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from praxis.core.interfaces import DataProvider

logger = logging.getLogger("praxis.data.registry")

# 健康检查阈值：连续失败 N 次标记为 unhealthy
FAILURE_THRESHOLD = 3


@dataclass
class ProviderEntry:
    """数据源注册条目"""
    name: str
    cls: type[DataProvider]
    priority: int = 50
    enabled: bool = True
    failure_count: int = 0
    healthy: bool = True

    @property
    def available(self) -> bool:
        return self.enabled and self.healthy


class ProviderRegistry:
    """数据源注册表"""

    def __init__(self):
        self._entries: dict[str, ProviderEntry] = {}
        self._instances: dict[str, DataProvider] = {}

    def register(
        self,
        name: str,
        cls: type[DataProvider],
        priority: int = 50,
        enabled: bool = True,
    ):
        """注册数据源"""
        self._entries[name] = ProviderEntry(
            name=name, cls=cls, priority=priority, enabled=enabled,
        )
        logger.info(f"注册数据源: {name} (优先级={priority}, 启用={enabled})")

    def unregister(self, name: str):
        """注销数据源"""
        self._entries.pop(name, None)
        instance = self._instances.pop(name, None)
        if instance:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(instance.close())
                else:
                    loop.run_until_complete(instance.close())
            except Exception:
                pass

    def get_instance(self, name: str) -> DataProvider | None:
        """获取数据源实例（单例）"""
        entry = self._entries.get(name)
        if not entry or not entry.available:
            return None
        if name not in self._instances:
            try:
                self._instances[name] = entry.cls()
            except Exception as e:
                logger.warning(f"数据源 {name} 实例化失败: {e}")
                entry.healthy = False
                return None
        return self._instances[name]

    def get_chain(self) -> list[tuple[str, DataProvider]]:
        """按优先级返回可用的数据源实例链"""
        available = sorted(
            [e for e in self._entries.values() if e.available],
            key=lambda e: e.priority,
        )
        result = []
        for entry in available:
            instance = self.get_instance(entry.name)
            if instance:
                result.append((entry.name, instance))
        return result

    def report_success(self, name: str):
        """报告成功调用（重置失败计数）"""
        entry = self._entries.get(name)
        if entry:
            entry.failure_count = 0
            entry.healthy = True

    def report_failure(self, name: str):
        """报告失败调用（累计到阈值后标记 unhealthy）"""
        entry = self._entries.get(name)
        if entry:
            entry.failure_count += 1
            if entry.failure_count >= FAILURE_THRESHOLD:
                entry.healthy = False
                logger.warning(
                    f"数据源 {name} 连续失败 {entry.failure_count} 次，标记为 unhealthy"
                )

    def list_providers(self) -> list[dict]:
        """列出所有注册的数据源"""
        return [
            {
                "name": e.name,
                "priority": e.priority,
                "enabled": e.enabled,
                "healthy": e.healthy,
                "available": e.available,
                "class": e.cls.__name__,
            }
            for e in sorted(self._entries.values(), key=lambda e: e.priority)
        ]

    def auto_discover(self, workspace: str = "."):
        """自动发现并注册所有数据源

        1. 注册内置数据源（尝试导入，失败则跳过）
        2. 扫描 providers/ 目录发现用户自定义数据源
        """
        self._discover_builtin()
        self._discover_plugins(workspace)

    def _discover_builtin(self):
        """发现内置数据源"""
        # 东方财富（零依赖，始终可用）
        try:
            from praxis.engine.data.eastmoney import EastMoneyDataProvider
            self.register("eastmoney", EastMoneyDataProvider, priority=50)
        except Exception as e:
            logger.warning(f"注册东方财富失败: {e}")

        # 腾讯（零依赖，始终可用）
        try:
            from praxis.engine.data.realtime import TencentDataProvider
            self.register("tencent", TencentDataProvider, priority=5)
        except Exception as e:
            logger.warning(f"注册腾讯失败: {e}")

        # AKShare（可选依赖）
        try:
            from praxis.engine.data.akshare_provider import AKShareDataProvider
            self.register("akshare", AKShareDataProvider, priority=10)
        except ImportError:
            logger.info("AKShare 未安装，跳过 (pip install praxis[akshare])")
        except Exception as e:
            logger.warning(f"注册 AKShare 失败: {e}")

        # Baostock（可选依赖）
        try:
            from praxis.engine.data.baostock_provider import BaostockProvider
            self.register("baostock", BaostockProvider, priority=30)
        except ImportError:
            logger.info("Baostock 未安装，跳过 (pip install praxis[baostock])")
        except Exception as e:
            logger.warning(f"注册 Baostock 失败: {e}")

    def _discover_plugins(self, workspace: str = "."):
        """扫描 providers/ 目录发现用户自定义数据源

        插件文件格式：
        - 文件名: *_provider.py 或 *.py（不以 _ 开头）
        - 必须包含一个继承 DataProvider 的类
        - 可选: priority = 30 类属性指定优先级

        安全：使用 spec_from_file_location 加载，不污染 sys.path
        """
        import importlib.util

        providers_dir = Path(workspace) / "providers"
        if not providers_dir.exists():
            return

        logger.info(f"扫描插件目录: {providers_dir.resolve()}")

        for py_file in sorted(providers_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem
            try:
                # 安全加载：不污染 sys.path，避免 stdlib 遮蔽
                spec = importlib.util.spec_from_file_location(
                    f"praxis.plugin.{module_name}", str(py_file)
                )
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # 查找继承 DataProvider 的类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, DataProvider)
                        and attr is not DataProvider
                    ):
                        priority = getattr(attr, "priority", 90)
                        self.register(
                            name=f"plugin:{module_name}",
                            cls=attr,
                            priority=priority,
                        )
                        logger.info(f"发现用户插件: {module_name}.{attr_name}")
            except Exception as e:
                logger.warning(f"加载插件 {module_name} 失败: {e}")

    def apply_config(self, config: dict):
        """从配置文件覆盖数据源优先级和启用状态

        支持两种配置格式:
        1. providers: {name: {enabled, priority}}
        2. provider_registry: {name: {enabled, priority}}
        """
        providers_config = config.get("provider_registry") or config.get("providers", {})
        for name, settings in providers_config.items():
            entry = self._entries.get(name)
            if entry:
                if "enabled" in settings:
                    entry.enabled = settings["enabled"]
                if "priority" in settings:
                    entry.priority = settings["priority"]
                logger.info(
                    f"配置覆盖: {name} enabled={entry.enabled} priority={entry.priority}"
                )

    async def close_all(self):
        """关闭所有数据源实例"""
        for name, instance in self._instances.items():
            try:
                await instance.close()
            except Exception:
                pass
        self._instances.clear()
