"""向后兼容重导出 — 从完整版 CachedDataProvider 导入

T02 将旧 stub 替换为完整实现。
"""
from praxis.engine.data.provider import CachedDataProvider

__all__ = ["CachedDataProvider"]
