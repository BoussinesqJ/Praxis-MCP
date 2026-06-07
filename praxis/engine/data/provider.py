"""统一数据源调度（多源容错 + 注册表驱动）

容错策略：按优先级链式降级 → 最终回退到本地缓存
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from praxis.core.interfaces import DataProvider
from praxis.core.models.error import DataError
from praxis.engine.data.registry import ProviderRegistry

logger = logging.getLogger("praxis.data.provider")


class CachedDataProvider(DataProvider):
    """带缓存的多源数据源调度器"""

    def __init__(
        self,
        cache_dir: Path | str | None = None,
        cache_ttl_seconds: int = 300,
        workspace: str = ".",
    ):
        self._registry = ProviderRegistry()
        self._registry.auto_discover(workspace)

        # 加载配置覆盖
        config_path = Path(workspace) / "config" / "data_sources.yaml"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                self._registry.apply_config(config)
            except Exception as e:
                logger.warning(f"加载数据源配置失败: {e}")

        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._cache_ttl = cache_ttl_seconds
        self._memory_cache: dict[str, dict] = {}

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情（链式容错）"""
        if not tickers:
            return {}

        chain = self._registry.get_chain()
        if not chain:
            logger.error("没有可用的数据源")
            return self._get_from_cache(tickers)

        for name, provider in chain:
            try:
                result = await provider.get_realtime_quote(tickers)
                if result:
                    self._registry.report_success(name)
                    self._memory_cache.update(result)
                    if self._cache_dir:
                        self._save_cache(result)
                    return result
            except Exception as e:
                logger.warning(f"数据源 {name} 失败: {e}")
                self._registry.report_failure(name)
                continue

        # 所有源都失败，回退到缓存
        logger.warning("所有数据源均失败，使用缓存")
        return self._get_from_cache(tickers)

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线（链式容错）"""
        chain = self._registry.get_chain()
        for name, provider in chain:
            try:
                result = await provider.get_history_kline(ticker, period, count)
                if result:
                    self._registry.report_success(name)
                    return result
            except Exception as e:
                logger.warning(f"数据源 {name} K线失败: {e}")
                self._registry.report_failure(name)
                continue
        return []

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值（链式容错）"""
        chain = self._registry.get_chain()
        for name, provider in chain:
            try:
                result = await provider.get_fund_nav(ticker)
                if result:
                    self._registry.report_success(name)
                    return result
            except Exception as e:
                logger.warning(f"数据源 {name} 基金净值失败: {e}")
                self._registry.report_failure(name)
                continue
        raise DataError(f"所有数据源均无法获取基金净值: {ticker}")

    def list_providers(self) -> list[dict]:
        """列出所有数据源状态"""
        return self._registry.list_providers()

    def _get_from_cache(self, tickers: list[str]) -> dict[str, dict]:
        """从缓存获取行情"""
        result = {}
        for ticker in tickers:
            if ticker in self._memory_cache:
                cached = self._memory_cache[ticker].copy()
                cached["is_stale"] = True
                result[ticker] = cached
        return result

    def _save_cache(self, data: dict[str, dict]):
        """保存到文件缓存"""
        if not self._cache_dir:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_dir / "realtime_cache.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    async def close(self):
        """关闭所有数据源"""
        await self._registry.close_all()
