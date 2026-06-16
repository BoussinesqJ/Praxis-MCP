"""全局限流器 - 令牌桶 + 随机抖动

基于 a-stock-data 的防封策略：
- 串行限流：间隔 ≥ 1s + 随机抖动
- 会话复用
- 封禁阈值：>5次/秒, ≥10并发, ≥200次/分, ≥300次/5分

使用方式：
    from praxis.core.rate_limiter import get_rate_limiter

    limiter = get_rate_limiter()
    async with limiter:
        # 执行请求
        pass
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("praxis.core.rate_limiter")


@dataclass
class RateLimitConfig:
    """限流器配置"""
    # 最小间隔（秒）
    min_interval: float = 1.0
    # 随机抖动最大值（秒）
    jitter_max: float = 0.5
    # 每秒最大请求数
    max_per_second: int = 5
    # 最大并发数
    max_concurrent: int = 10
    # 每分钟最大请求数
    max_per_minute: int = 200
    # 每5分钟最大请求数
    max_per_5min: int = 300


class RateLimiter:
    """全局限流器（令牌桶 + 随机抖动）

    实现原理：
    1. 令牌桶：控制请求速率
    2. 随机抖动：避免请求集中
    3. 并发控制：限制同时进行的请求数
    4. 滑动窗口：跟踪历史请求频率
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()

        # 并发控制
        self._current_concurrent = 0
        self._concurrent_semaphore = asyncio.Semaphore(self.config.max_concurrent)

        # 时间控制
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()

        # 频率跟踪（滑动窗口）
        self._request_timestamps: list[float] = []

        # 统计信息
        self._total_requests = 0
        self._total_wait_time = 0.0

    async def acquire(self) -> None:
        """获取令牌（等待直到可以发送请求）

        Raises:
            RateLimitExceeded: 超过频率限制
        """
        start_time = time.time()

        # 1. 并发控制
        await self._concurrent_semaphore.acquire()
        self._current_concurrent += 1

        # 2. 时间间隔控制
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time

            if elapsed < self.config.min_interval:
                # 计算需要等待的时间
                wait_time = self.config.min_interval - elapsed

                # 添加随机抖动
                if self.config.jitter_max > 0:
                    jitter = random.uniform(0, self.config.jitter_max)
                    wait_time += jitter

                logger.debug(f"限流等待: {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

            self._last_request_time = time.time()

        # 3. 频率检查
        self._clean_old_timestamps()
        if len(self._request_timestamps) >= self.config.max_per_minute:
            self._current_concurrent -= 1
            self._concurrent_semaphore.release()
            raise RateLimitExceeded("超过每分钟请求限制")

        # 4. 记录请求
        self._request_timestamps.append(time.time())
        self._total_requests += 1
        self._total_wait_time += time.time() - start_time

    def release(self) -> None:
        """释放令牌"""
        if self._current_concurrent > 0:
            self._current_concurrent -= 1
            self._concurrent_semaphore.release()

    async def __aenter__(self) -> RateLimiter:
        """异步上下文管理器入口"""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        self.release()

    def _clean_old_timestamps(self) -> None:
        """清理过期的时间戳（保留最近5分钟）"""
        cutoff = time.time() - 300  # 5分钟
        self._request_timestamps = [
            ts for ts in self._request_timestamps if ts > cutoff
        ]

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_requests": self._total_requests,
            "total_wait_time": round(self._total_wait_time, 2),
            "current_concurrent": self._current_concurrent,
            "requests_last_minute": len([
                ts for ts in self._request_timestamps
                if ts > time.time() - 60
            ]),
            "requests_last_5min": len(self._request_timestamps),
        }

    def reset(self) -> None:
        """重置统计信息"""
        self._total_requests = 0
        self._total_wait_time = 0.0
        self._request_timestamps.clear()
        self._last_request_time = 0.0


class RateLimitExceeded(Exception):
    """超过频率限制异常"""
    pass


# 全局单例
_global_limiter: Optional[RateLimiter] = None
_limiter_lock = asyncio.Lock()


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """获取全局限流器单例

    Args:
        config: 限流器配置（仅首次调用时生效）

    Returns:
        全局限流器实例
    """
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter(config)
    return _global_limiter


def reset_rate_limiter() -> None:
    """重置全局限流器（主要用于测试）"""
    global _global_limiter
    _global_limiter = None
