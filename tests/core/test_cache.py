"""本地 TTL 缓存层单元测试

测试基于 TTL 的本地缓存机制
"""
import asyncio
import json
import os
import tempfile
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from praxis.core.cache import TTLCache, CacheConfig


class TestTTLCache:
    """TTL 缓存测试"""

    def test_default_config(self):
        """测试默认配置"""
        cache = TTLCache("test")
        assert cache.config.default_ttl == 3600  # 1小时
        assert cache.config.max_size == 1000

    def test_custom_config(self):
        """测试自定义配置"""
        config = CacheConfig(
            default_ttl=7200,
            max_size=500,
            cache_dir="/tmp/test_cache"
        )
        cache = TTLCache("test", config)
        assert cache.config.default_ttl == 7200
        assert cache.config.max_size == 500

    def test_set_and_get(self):
        """测试设置和获取"""
        cache = TTLCache("test")
        cache.set("key1", {"data": "value1"})
        result = cache.get("key1")
        assert result == {"data": "value1"}

    def test_get_nonexistent(self):
        """测试获取不存在的键"""
        cache = TTLCache("test")
        result = cache.get("nonexistent")
        assert result is None

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        config = CacheConfig(default_ttl=1)  # 1秒过期
        cache = TTLCache("test", config)

        cache.set("key1", {"data": "value1"})
        assert cache.get("key1") == {"data": "value1"}

        # 等待过期
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        """测试自定义 TTL"""
        cache = TTLCache("test")

        # 设置 2 秒 TTL
        cache.set("key1", {"data": "value1"}, ttl=2)
        assert cache.get("key1") == {"data": "value1"}

        # 1 秒后仍有效
        time.sleep(1)
        assert cache.get("key1") == {"data": "value1"}

        # 2 秒后过期
        time.sleep(1.1)
        assert cache.get("key1") is None

    def test_delete(self):
        """测试删除"""
        cache = TTLCache("test")
        cache.set("key1", {"data": "value1"})
        assert cache.get("key1") == {"data": "value1"}

        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        """测试清空"""
        cache = TTLCache("test")
        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})

        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_has(self):
        """测试检查键是否存在"""
        cache = TTLCache("test")
        cache.set("key1", {"data": "value1"})

        assert cache.has("key1") is True
        assert cache.has("nonexistent") is False

    def test_has_expired(self):
        """测试检查过期键"""
        config = CacheConfig(default_ttl=1)
        cache = TTLCache("test", config)

        cache.set("key1", {"data": "value1"})
        assert cache.has("key1") is True

        time.sleep(1.1)
        assert cache.has("key1") is False

    def test_size_limit(self):
        """测试大小限制"""
        config = CacheConfig(max_size=3)
        cache = TTLCache("test", config)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # 应该淘汰 key1

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_stats(self):
        """测试统计信息"""
        cache = TTLCache("test")
        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("nonexistent")

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_persistence(self):
        """测试持久化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = CacheConfig(cache_dir=tmpdir, enable_persistence=True)
            cache = TTLCache("test", config)

            # 写入数据
            cache.set("key1", {"data": "value1"})
            cache.save()

            # 创建新缓存实例
            cache2 = TTLCache("test", config)
            cache2.load()

            assert cache2.get("key1") == {"data": "value1"}


class TestTTLCacheSingleton:
    """测试全局单例"""

    def test_singleton(self):
        """测试全局单例"""
        from praxis.core.cache import get_cache, reset_cache

        reset_cache()
        cache1 = get_cache("test")
        cache2 = get_cache("test")

        assert cache1 is cache2
        reset_cache()

    def test_different_namespaces(self):
        """测试不同命名空间"""
        from praxis.core.cache import get_cache, reset_cache

        reset_cache()
        cache1 = get_cache("test1")
        cache2 = get_cache("test2")

        assert cache1 is not cache2
        reset_cache()
