"""熔断器机制 - 连续失败自动冷却

基于 Gemini 架构审查决断：
- 任何底层请求捕获到 Timeout 或 403 时，记录错误
- 某节点连续失败 3 次，立刻将其标记为 Cooling Down（冷却，如 10 分钟）
- 系统自动无缝切向下一个优先级的备用数据源

使用方式：
    from praxis.core.circuit_breaker import get_registry

    registry = get_registry()
    cb = registry.get_or_create("eastmoney")

    if cb.is_available():
        with cb:
            # 执行请求
            pass
    else:
        # 使用备用数据源
        pass
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("praxis.core.circuit_breaker")


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 正常（允许请求）
    OPEN = "open"  # 熔断（拒绝请求）
    HALF_OPEN = "half_open"  # 半开（试探请求）


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    # 失败阈值（连续失败次数）
    failure_threshold: int = 3
    # 冷却时间（秒）
    cooldown_seconds: int = 600  # 10分钟
    # 成功阈值（半开状态成功次数）
    success_threshold: int = 2


class CircuitBreakerOpen(Exception):
    """熔断器打开异常"""
    pass


class CircuitBreaker:
    """熔断器

    状态机：
    CLOSED -> (连续失败 >= threshold) -> OPEN
    OPEN -> (冷却时间结束) -> HALF_OPEN
    HALF_OPEN -> (连续成功 >= success_threshold) -> CLOSED
    HALF_OPEN -> (失败) -> OPEN
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._opened_at = 0.0

    @property
    def state(self) -> CircuitState:
        """获取当前状态（自动检查冷却）"""
        if self._state == CircuitState.OPEN:
            # 检查冷却时间是否结束
            if self._last_failure_time > 0:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.config.cooldown_seconds:
                    logger.info(f"熔断器 [{self.name}] 冷却结束，进入半开状态")
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_count(self) -> int:
        return self._success_count

    def record_success(self) -> None:
        """记录成功"""
        self._success_count += 1
        self._failure_count = 0  # 重置连续失败计数

        if self._state == CircuitState.HALF_OPEN:
            if self._success_count >= self.config.success_threshold:
                logger.info(f"熔断器 [{self.name}] 半开状态成功，恢复正常")
                self._state = CircuitState.CLOSED
                self._success_count = 0

    def record_failure(self) -> None:
        """记录失败"""
        self._failure_count += 1
        self._success_count = 0  # 重置连续成功计数
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            # 半开状态失败，重新打开
            logger.warning(f"熔断器 [{self.name}] 半开状态失败，重新熔断")
            self._state = CircuitState.OPEN
            self._opened_at = time.time()
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                logger.warning(
                    f"熔断器 [{self.name}] 连续失败 {self._failure_count} 次，熔断 "
                    f"{self.config.cooldown_seconds} 秒"
                )
                self._state = CircuitState.OPEN
                self._opened_at = time.time()

    def is_available(self) -> bool:
        """检查是否可用"""
        state = self.state  # 触发冷却检查
        return state != CircuitState.OPEN

    def __enter__(self) -> CircuitBreaker:
        """上下文管理器入口"""
        if not self.is_available():
            raise CircuitBreakerOpen(
                f"熔断器 [{self.name}] 处于打开状态，"
                f"冷却剩余 {self._cooldown_remaining():.0f} 秒"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        if exc_type is not None:
            self.record_failure()
        else:
            self.record_success()
        return None  # 不抑制异常

    def _cooldown_remaining(self) -> float:
        """计算冷却剩余时间"""
        if self._state != CircuitState.OPEN:
            return 0.0
        elapsed = time.time() - self._last_failure_time
        remaining = self.config.cooldown_seconds - elapsed
        return max(0.0, remaining)

    def reset(self) -> None:
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._opened_at = 0.0

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "cooldown_remaining": round(self._cooldown_remaining(), 1),
        }


class CircuitBreakerRegistry:
    """熔断器注册表"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self, name: str, config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get_all(self) -> dict[str, CircuitBreaker]:
        """获取所有熔断器"""
        return self._breakers.copy()

    def reset_all(self) -> None:
        """重置所有熔断器"""
        for cb in self._breakers.values():
            cb.reset()


# 全局注册表
_global_registry: Optional[CircuitBreakerRegistry] = None


def get_registry() -> CircuitBreakerRegistry:
    """获取全局熔断器注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = CircuitBreakerRegistry()
    return _global_registry


def reset_registry() -> None:
    """重置全局注册表（主要用于测试）"""
    global _global_registry
    _global_registry = None
