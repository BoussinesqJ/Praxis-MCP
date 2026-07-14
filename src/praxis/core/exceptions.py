"""PRAXIS 异常体系

统一定义各层使用的异常类，避免散落在各模块中。

层级:
    PraxisError           — 所有 PRAXIS 异常的基类
    ├── DataError         — 数据获取/解析失败（数据源层）
    ├── ConfigError       — 配置加载/校验失败
    └── ProviderError     — 数据源注册/实例化失败
"""

from __future__ import annotations


class PraxisError(Exception):
    """PRAXIS 所有异常的基类

    Attributes:
        message: 错误描述
        source: 错误来源标识（如数据源名称）
    """

    def __init__(self, message: str, source: str = "", path: str = "") -> None:
        self.source = source
        self.path = path
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        if self.source:
            return f"[{self.source}] {self.message}"
        return self.message


class DataError(PraxisError):
    """数据获取或解析失败异常

    用于 DataProvider 实现在请求外部数据源失败时抛出，
    上层调度器（CachedDataProvider）会捕获并触发降级。

    Args:
        message: 错误描述
        source: 数据源名称（如 "tencent"、"mootdx"）
    """

    pass


class ConfigError(PraxisError):
    """配置加载或校验失败异常"""

    pass


class ProviderError(PraxisError):
    """数据源注册或实例化失败异常"""

    pass
