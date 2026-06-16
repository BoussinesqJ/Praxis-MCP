"""东财统一客户端基类

基于 Gemini Phase 2 建议：
- 自动注入伪装的 User-Agent
- 自动管理 Session Cookies
- 强制包裹全局限流器 rate_limiter
- 所有东财 API 调用必须继承此基类
- 严禁在业务层直接手写 requests.get("eastmoney.com")

使用方式：
    from praxis.core.em_client import get_em_client

    client = get_em_client()
    data = await client.get("https://push2.eastmoney.com/api/qt/...")
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from praxis.core.cache import TTLCache, get_cache, EASTMONEY_CACHE_CONFIG
from praxis.core.rate_limiter import get_rate_limiter

logger = logging.getLogger("praxis.core.em_client")


@dataclass
class EMClientConfig:
    """东财客户端配置"""
    # 最小请求间隔（秒）
    min_interval: float = 1.0
    # 随机抖动最大值（秒）
    jitter_max: float = 0.5
    # 请求超时（秒）
    timeout: int = 10
    # 最大重试次数
    max_retries: int = 3
    # 是否启用缓存
    enable_cache: bool = True


class EMClient:
    """东财统一客户端

    功能：
    1. 自动注入伪装的 User-Agent
    2. 自动管理 Session Cookies
    3. 集成全局限流器
    4. 集成 TTL 缓存
    5. 自动重试机制
    """

    def __init__(self, config: Optional[EMClientConfig] = None):
        self.config = config or EMClientConfig()
        self._session: Optional[requests.Session] = None
        self._rate_limiter = get_rate_limiter()
        self._cache: Optional[TTLCache] = None

        if self.config.enable_cache:
            self._cache = get_cache("eastmoney", EASTMONEY_CACHE_CONFIG)

    def _get_user_agent(self) -> str:
        """获取随机 User-Agent"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        return random.choice(user_agents)

    def _get_session(self) -> requests.Session:
        """获取或创建 Session"""
        if self._session is None:
            self._session = requests.Session()
            self._session.trust_env = False
            self._session.proxies = {'http': None, 'https': None}

            # 设置默认 headers
            self._session.headers.update({
                "User-Agent": self._get_user_agent(),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Referer": "https://data.eastmoney.com/",
            })

        return self._session

    async def get(
        self,
        url: str,
        params: Optional[dict] = None,
        cache_key: Optional[str] = None,
        cache_ttl: Optional[int] = None,
    ) -> Any:
        """发送 GET 请求（带限流 + 缓存 + 重试）

        Args:
            url: 请求 URL
            params: 请求参数
            cache_key: 缓存键（None 不使用缓存）
            cache_ttl: 缓存 TTL（秒）

        Returns:
            JSON 响应数据

        Raises:
            Exception: 请求失败
        """
        # 1. 检查缓存
        if cache_key and self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return cached

        # 2. 限流等待
        async with self._rate_limiter:
            # 3. 重试机制
            last_exception = None
            for attempt in range(self.config.max_retries):
                try:
                    session = self._get_session()

                    # 添加随机抖动
                    if attempt > 0:
                        jitter = random.uniform(0, self.config.jitter_max)
                        time.sleep(jitter)

                    # 发送请求
                    resp = session.get(
                        url,
                        params=params,
                        timeout=self.config.timeout,
                    )
                    resp.raise_for_status()

                    # 解析响应
                    result = resp.json()

                    # 4. 写入缓存
                    if cache_key and self._cache:
                        self._cache.set(cache_key, result, cache_ttl)
                        logger.debug(f"缓存写入: {cache_key}")

                    return result

                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"东财请求失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}"
                    )
                    continue

            # 所有重试都失败
            raise last_exception

    async def get_text(
        self,
        url: str,
        params: Optional[dict] = None,
        cache_key: Optional[str] = None,
        cache_ttl: Optional[int] = None,
    ) -> str:
        """发送 GET 请求并返回文本响应

        Args:
            url: 请求 URL
            params: 请求参数
            cache_key: 缓存键
            cache_ttl: 缓存 TTL

        Returns:
            文本响应
        """
        # 1. 检查缓存
        if cache_key and self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        # 2. 限流等待
        async with self._rate_limiter:
            # 3. 重试机制
            last_exception = None
            for attempt in range(self.config.max_retries):
                try:
                    session = self._get_session()

                    # 添加随机抖动
                    if attempt > 0:
                        jitter = random.uniform(0, self.config.jitter_max)
                        time.sleep(jitter)

                    # 发送请求
                    resp = session.get(
                        url,
                        params=params,
                        timeout=self.config.timeout,
                    )
                    resp.raise_for_status()

                    result = resp.text

                    # 4. 写入缓存
                    if cache_key and self._cache:
                        self._cache.set(cache_key, result, cache_ttl)

                    return result

                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"东财请求失败 (尝试 {attempt + 1}/{self.config.max_retries}): {e}"
                    )
                    continue

            raise last_exception

    def close(self) -> None:
        """关闭 Session"""
        if self._session:
            self._session.close()
            self._session = None


# 全局单例
_global_client: Optional[EMClient] = None


def get_em_client(config: Optional[EMClientConfig] = None) -> EMClient:
    """获取东财客户端单例

    Args:
        config: 客户端配置（仅首次调用时生效）

    Returns:
        东财客户端实例
    """
    global _global_client
    if _global_client is None:
        _global_client = EMClient(config)
    return _global_client


def reset_em_client() -> None:
    """重置东财客户端（主要用于测试）"""
    global _global_client
    if _global_client:
        _global_client.close()
    _global_client = None
