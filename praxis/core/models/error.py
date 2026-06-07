"""PRAXIS 错误模型"""
from __future__ import annotations


class PraxisError(Exception):
    """PRAXIS 基础异常"""

    def __init__(self, message: str, code: str = "PRAXIS_ERROR", details: dict | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigError(PraxisError):
    """配置错误"""
    def __init__(self, message: str, path: str = "", **kwargs):
        super().__init__(message, code="CONFIG_ERROR", details={"path": path, **kwargs})


class DataError(PraxisError):
    """数据错误（行情/API）"""
    def __init__(self, message: str, source: str = "", **kwargs):
        super().__init__(message, code="DATA_ERROR", details={"source": source, **kwargs})


class ReconcileError(PraxisError):
    """对账错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="RECONCILE_ERROR", details=kwargs)


class LedgerError(PraxisError):
    """账本错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code="LEDGER_ERROR", details=kwargs)


class ConstraintViolation(PraxisError):
    """约束违反"""
    def __init__(self, message: str, rule: str = "", severity: str = "block", **kwargs):
        super().__init__(message, code="CONSTRAINT_VIOLATION", details={"rule": rule, "severity": severity, **kwargs})
