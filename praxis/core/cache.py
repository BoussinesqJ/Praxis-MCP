"""本地 TTL 缓存层

基于 Gemini Phase 2 建议：
- 相同标的的研报和龙虎榜数据，在 12 小时内严禁重复向东方财富发起 HTTP 请求
- 最大限度节约限流器的"令牌"

使用方式：
    from praxis.core.cache import get_cache

    cache = get_cache("eastmoney")
    
    # 检查缓存
    data = cache.get("report_000001")
    if data is None:
        # 缓存未命中，请求数据
        data = fetch_report("000001")
        cache.set("report_000001", data, ttl=43200)  # 12小时
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("praxis.core.cache")


@dataclass
class CacheConfig:
    """缓存配置"""
    # 默认 TTL（秒）
    default_ttl: int = 3600  # 1小时
    # 最大缓存条目数
    max_size: int = 1000
    # 缓存目录（持久化）
    cache_dir: Optional[str] = None
    # 是否启用持久化
    enable_persistence: bool = False


class TTLCache:
    """基于 TTL 的本地缓存

    特性：
    1. TTL 过期自动清理
    2. LRU 淘汰策略
    3. 可选持久化到 JSON 文件
    4. 命中率统计
    """

    def __init__(self, namespace: str, config: Optional[CacheConfig] = None):
        self.namespace = namespace
        self.config = config or CacheConfig()

        # 缓存数据: {key: (value, expire_time)}
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()

        # 统计信息
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或已过期则返回 None
        """
        full_key = f"{self.namespace}:{key}"

        if full_key not in self._cache:
            self._misses += 1
            return None

        value, expire_time = self._cache[full_key]

        # 检查是否过期
        if time.time() > expire_time:
            self._misses += 1
            self.delete(key)
            return None

        self._hits += 1
        # 移到末尾（LRU）
        self._cache.move_to_end(full_key)
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 使用默认 TTL
        """
        full_key = f"{self.namespace}:{key}"
        ttl = ttl or self.config.default_ttl
        expire_time = time.time() + ttl

        # 如果已存在，先删除
        if full_key in self._cache:
            del self._cache[full_key]

        # 添加新值
        self._cache[full_key] = (value, expire_time)

        # 检查大小限制
        while len(self._cache) > self.config.max_size:
            # 淘汰最旧的条目
            self._cache.popitem(last=False)

    def delete(self, key: str) -> None:
        """删除缓存值

        Args:
            key: 缓存键
        """
        full_key = f"{self.namespace}:{key}"
        if full_key in self._cache:
            del self._cache[full_key]

    def clear(self) -> None:
        """清空缓存"""
        # 只清空当前命名空间的缓存
        keys_to_delete = [
            k for k in self._cache.keys()
            if k.startswith(f"{self.namespace}:")
        ]
        for key in keys_to_delete:
            del self._cache[key]

    def has(self, key: str) -> bool:
        """检查键是否存在且未过期

        Args:
            key: 缓存键

        Returns:
            是否存在
        """
        return self.get(key) is not None

    def get_stats(self) -> dict:
        """获取统计信息"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0

        return {
            "namespace": self.namespace,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "size": len(self._cache),
            "max_size": self.config.max_size,
        }

    def save(self) -> None:
        """保存缓存到文件"""
        if not self.config.enable_persistence or not self.config.cache_dir:
            return

        cache_dir = Path(self.config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache_file = cache_dir / f"{self.namespace}.json"

        # 序列化缓存数据
        data = {}
        current_time = time.time()
        for key, (value, expire_time) in self._cache.items():
            if expire_time > current_time:
                # 只保存未过期的数据
                short_key = key.replace(f"{self.namespace}:", "")
                data[short_key] = {
                    "value": value,
                    "expire_time": expire_time,
                }

        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"缓存已保存到 {cache_file}")

    def load(self) -> None:
        """从文件加载缓存"""
        if not self.config.enable_persistence or not self.config.cache_dir:
            return

        cache_file = Path(self.config.cache_dir) / f"{self.namespace}.json"

        if not cache_file.exists():
            return

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            current_time = time.time()
            loaded_count = 0

            for short_key, item in data.items():
                expire_time = item["expire_time"]
                if expire_time > current_time:
                    full_key = f"{self.namespace}:{short_key}"
                    self._cache[full_key] = (item["value"], expire_time)
                    loaded_count += 1

            logger.info(f"从 {cache_file} 加载了 {loaded_count} 条缓存")
        except Exception as e:
            logger.warning(f"加载缓存失败: {e}")


# 全局缓存实例
_caches: dict[str, TTLCache] = {}


def get_cache(namespace: str, config: Optional[CacheConfig] = None) -> TTLCache:
    """获取缓存实例

    Args:
        namespace: 命名空间（如 "eastmoney", "ths"）
        config: 缓存配置（仅首次调用时生效）

    Returns:
        缓存实例
    """
    if namespace not in _caches:
        _caches[namespace] = TTLCache(namespace, config)
    return _caches[namespace]


def reset_cache(namespace: Optional[str] = None) -> None:
    """重置缓存（主要用于测试）

    Args:
        namespace: 命名空间，None 重置所有
    """
    global _caches
    if namespace:
        if namespace in _caches:
            del _caches[namespace]
    else:
        _caches.clear()


# 预定义的缓存配置
EASTMONEY_CACHE_CONFIG = CacheConfig(
    default_ttl=43200,  # 12小时
    max_size=500,
    enable_persistence=True,
    cache_dir="cache/eastmoney",
)

THS_CACHE_CONFIG = CacheConfig(
    default_ttl=43200,  # 12小时
    max_size=500,
    enable_persistence=True,
    cache_dir="cache/ths",
)

REALTIME_CACHE_CONFIG = CacheConfig(
    default_ttl=60,  # 1分钟
    max_size=1000,
    enable_persistence=False,
)
