"""熔断器单元测试

测试连续失败自动冷却机制
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch

from praxis.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpen,
)


class TestCircuitBreaker:
    """熔断器测试"""

    def test_default_config(self):
        """测试默认配置"""
        cb = CircuitBreaker("test")
        assert cb.config.failure_threshold == 3
        assert cb.config.cooldown_seconds == 600  # 10分钟
        assert cb.config.success_threshold == 2

    def test_custom_config(self):
        """测试自定义配置"""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            cooldown_seconds=300,
            success_threshold=3
        )
        cb = CircuitBreaker("test", config)
        assert cb.config.failure_threshold == 5
        assert cb.config.cooldown_seconds == 300
        assert cb.config.success_threshold == 3

    def test_initial_state(self):
        """测试初始状态"""
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_record_success(self):
        """测试记录成功"""
        cb = CircuitBreaker("test")
        cb.record_success()
        assert cb.success_count == 1
        assert cb.failure_count == 0

    def test_record_failure(self):
        """测试记录失败"""
        cb = CircuitBreaker("test")
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.success_count == 0

    def test_open_after_threshold(self):
        """测试达到阈值后打开熔断器"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config)

        # 记录 3 次失败
        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_open_cooldown(self):
        """测试冷却时间"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            cooldown_seconds=1  # 1秒冷却
        )
        cb = CircuitBreaker("test", config)

        # 触发熔断
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 冷却期间应保持打开
        assert cb.state == CircuitState.OPEN

        # 等待冷却
        time.sleep(1.1)

        # 冷却后应变为半开
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed(self):
        """测试半开状态到关闭"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            cooldown_seconds=1,
            success_threshold=2
        )
        cb = CircuitBreaker("test", config)

        # 触发熔断
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 等待冷却
        time.sleep(1.1)
        assert cb.state == CircuitState.HALF_OPEN

        # 记录 2 次成功
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open(self):
        """测试半开状态再次失败"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            cooldown_seconds=1
        )
        cb = CircuitBreaker("test", config)

        # 触发熔断
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # 等待冷却
        time.sleep(1.1)
        assert cb.state == CircuitState.HALF_OPEN

        # 再次失败
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_is_available_closed(self):
        """测试关闭状态可用"""
        cb = CircuitBreaker("test")
        assert cb.is_available() is True

    def test_is_available_open(self):
        """测试打开状态不可用"""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    def test_is_available_half_open(self):
        """测试半开状态可用"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            cooldown_seconds=1
        )
        cb = CircuitBreaker("test", config)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(1.1)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.is_available() is True

    def test_reset(self):
        """测试重置"""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_get_stats(self):
        """测试统计信息"""
        cb = CircuitBreaker("test")
        cb.record_failure()
        cb.record_success()

        stats = cb.get_stats()
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0  # record_success 重置连续失败计数
        assert stats["success_count"] == 1

    def test_context_manager_success(self):
        """测试上下文管理器成功"""
        cb = CircuitBreaker("test")

        with cb:
            pass  # 成功

        assert cb.success_count == 1
        assert cb.failure_count == 0

    def test_context_manager_failure(self):
        """测试上下文管理器失败"""
        config = CircuitBreakerConfig(failure_threshold=2)
        cb = CircuitBreaker("test")

        with pytest.raises(ValueError):
            with cb:
                raise ValueError("test error")

        assert cb.failure_count == 1

    def test_context_manager_open(self):
        """测试打开状态使用上下文管理器"""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker("test", config)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerOpen):
            with cb:
                pass


class TestCircuitBreakerRegistry:
    """熔断器注册表测试"""

    def test_get_or_create(self):
        """测试获取或创建"""
        from praxis.core.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()
        cb1 = registry.get_or_create("test")
        cb2 = registry.get_or_create("test")

        assert cb1 is cb2

    def test_get_all(self):
        """测试获取所有"""
        from praxis.core.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()
        registry.get_or_create("test1")
        registry.get_or_create("test2")

        all_cbs = registry.get_all()
        assert len(all_cbs) == 2
        assert "test1" in all_cbs
        assert "test2" in all_cbs

    def test_reset_all(self):
        """测试重置所有"""
        from praxis.core.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()
        cb1 = registry.get_or_create("test1")
        cb2 = registry.get_or_create("test2")

        cb1.record_failure()
        cb2.record_failure()

        registry.reset_all()

        assert cb1.state == CircuitState.CLOSED
        assert cb2.state == CircuitState.CLOSED


class TestGlobalRegistry:
    """测试全局注册表"""

    def test_global_singleton(self):
        """测试全局单例"""
        from praxis.core.circuit_breaker import get_registry, reset_registry

        reset_registry()
        reg1 = get_registry()
        reg2 = get_registry()

        assert reg1 is reg2
        reset_registry()
