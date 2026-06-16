"""全局限流器单元测试

测试令牌桶 + 随机抖动机制
"""
import asyncio
import time
import pytest
from unittest.mock import patch, AsyncMock

from praxis.core.rate_limiter import RateLimiter, RateLimitConfig


class TestRateLimiter:
    """全局限流器测试"""

    def test_default_config(self):
        """测试默认配置"""
        limiter = RateLimiter()
        assert limiter.config.min_interval == 1.0
        assert limiter.config.jitter_max == 0.5
        assert limiter.config.max_per_second == 5
        assert limiter.config.max_concurrent == 10

    def test_custom_config(self):
        """测试自定义配置"""
        config = RateLimitConfig(
            min_interval=2.0,
            jitter_max=1.0,
            max_per_second=3,
            max_concurrent=5
        )
        limiter = RateLimiter(config)
        assert limiter.config.min_interval == 2.0
        assert limiter.config.jitter_max == 1.0
        assert limiter.config.max_per_second == 3
        assert limiter.config.max_concurrent == 5

    @pytest.mark.asyncio
    async def test_acquire_immediate(self):
        """测试首次获取令牌应立即通过"""
        limiter = RateLimiter()
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start
        assert elapsed < 0.1  # 应立即通过

    @pytest.mark.asyncio
    async def test_acquire_respects_min_interval(self):
        """测试最小间隔限制"""
        config = RateLimitConfig(min_interval=0.5, jitter_max=0.0)
        limiter = RateLimiter(config)

        # 第一次获取
        await limiter.acquire()

        # 第二次获取应等待
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed >= 0.5  # 应等待至少 0.5 秒

    @pytest.mark.asyncio
    async def test_acquire_with_jitter(self):
        """测试随机抖动"""
        config = RateLimitConfig(min_interval=0.5, jitter_max=0.3)
        limiter = RateLimiter(config)

        # 第一次获取
        await limiter.acquire()

        # 第二次获取应等待（0.5 + 0~0.3 秒）
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed >= 0.5
        assert elapsed <= 0.9  # 0.5 + 0.3 + 误差

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        """测试并发限制"""
        config = RateLimitConfig(max_concurrent=2, min_interval=0.0)
        limiter = RateLimiter(config)

        # 获取 2 个令牌
        await limiter.acquire()
        await limiter.acquire()

        # 第 3 个应被阻塞
        async def third_acquire():
            await limiter.acquire()
            return True

        task = asyncio.create_task(third_acquire())

        # 等待一小段时间，任务应被阻塞
        await asyncio.sleep(0.1)
        assert not task.done()

        # 释放一个令牌
        limiter.release()

        # 等待任务完成
        result = await asyncio.wait_for(task, timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_release(self):
        """测试释放令牌"""
        config = RateLimitConfig(max_concurrent=1, min_interval=0.0)
        limiter = RateLimiter(config)

        # 获取令牌
        await limiter.acquire()
        assert limiter._current_concurrent == 1

        # 释放令牌
        limiter.release()
        assert limiter._current_concurrent == 0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试上下文管理器"""
        config = RateLimitConfig(max_concurrent=1, min_interval=0.0)
        limiter = RateLimiter(config)

        async with limiter:
            assert limiter._current_concurrent == 1

        assert limiter._current_concurrent == 0

    @pytest.mark.asyncio
    async def test_rate_limit_tracking(self):
        """测试频率限制跟踪"""
        config = RateLimitConfig(max_per_second=3, min_interval=0.0)
        limiter = RateLimiter(config)

        # 快速获取 3 个令牌
        for _ in range(3):
            await limiter.acquire()
            limiter.release()

        # 检查频率计数
        assert limiter._total_requests == 3

    @pytest.mark.asyncio
    async def test_statistics(self):
        """测试统计信息"""
        limiter = RateLimiter()

        # 执行一些操作
        await limiter.acquire()
        limiter.release()
        await limiter.acquire()
        limiter.release()

        stats = limiter.get_stats()
        assert stats["total_requests"] == 2
        assert stats["total_wait_time"] >= 0
        assert stats["current_concurrent"] == 0

    @pytest.mark.asyncio
    async def test_reset(self):
        """测试重置"""
        limiter = RateLimiter()

        # 执行一些操作
        await limiter.acquire()
        await limiter.acquire()

        # 重置
        limiter.reset()

        stats = limiter.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_wait_time"] == 0


class TestRateLimiterSingleton:
    """测试全局单例"""

    def test_singleton_instance(self):
        """测试全局单例"""
        from praxis.core.rate_limiter import get_rate_limiter

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_singleton_with_config(self):
        """测试带配置的单例"""
        from praxis.core.rate_limiter import get_rate_limiter, reset_rate_limiter

        reset_rate_limiter()

        config = RateLimitConfig(min_interval=2.0)
        limiter1 = get_rate_limiter(config)
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2
        assert limiter1.config.min_interval == 2.0

        reset_rate_limiter()
