"""iwen财数据源

基于 Gemini Phase 3 建议：
- 红线：严禁尝试用 requests 或 httpx 手工逆向 Hexin-V 加密参数
- 方案 1 (推荐)：使用 Playwright 无头浏览器
- 方案 2 (妥协)：使用 akshare 现成接口作为黑盒

使用方式：
    from providers.iwencai_provider import IwencaiProvider

    provider = IwencaiProvider()
    
    # 自然语言搜索
    result = await provider.search("银行股 涨幅超过3%")
"""
from __future__ import annotations

import logging
from typing import Optional

from praxis.core.cache import TTLCache, get_cache, CacheConfig

logger = logging.getLogger("praxis.provider.iwencai")

# 缓存配置（1小时）
IWENCAI_CACHE_CONFIG = CacheConfig(
    default_ttl=3600,  # 1小时
    max_size=100,
    enable_persistence=True,
    cache_dir="cache/iwencai",
)


class IwencaiProvider:
    """iwen财数据源

    降级策略：
    1. 优先使用 akshare（方案 2 - 妥协）
    2. 失败时降级到 Playwright（方案 1 - 推荐）
    3. 都失败则返回空

    注意：
    - 严禁手工逆向 Hexin-V 加密参数
    - Playwright 方案资源消耗较大，仅作为备用
    """

    def __init__(self):
        # 缓存
        self._cache = get_cache("iwencai", IWENCAI_CACHE_CONFIG)

        # Playwright 实例（懒加载）
        self._playwright = None
        self._browser = None

    async def search(self, query: str) -> list[dict]:
        """自然语言搜索

        Args:
            query: 自然语言查询（如 "银行股 涨幅超过3%"）

        Returns:
            搜索结果列表
        """
        # 构建缓存键
        cache_key = f"search:{query}"

        # 检查缓存
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug(f"缓存命中: {cache_key}")
            return cached

        # 方案 1：尝试 akshare
        try:
            result = self._search_with_akshare(query)
            if result:
                self._cache.set(cache_key, result, ttl=3600)
                return result
        except Exception as e:
            logger.warning(f"akshare 搜索失败: {e}")

        # 方案 2：降级到 Playwright
        try:
            result = await self._search_with_playwright(query)
            if result:
                self._cache.set(cache_key, result, ttl=3600)
                return result
        except Exception as e:
            logger.warning(f"Playwright 搜索失败: {e}")

        # 所有方法都失败
        logger.warning(f"iwen财搜索失败: {query}")
        return []

    def _search_with_akshare(self, query: str) -> list[dict]:
        """使用 akshare 搜索（方案 2 - 妥协）

        akshare 封装了同花顺问财的接口，作为黑盒使用。
        """
        try:
            import akshare as ak

            # 使用 akshare 的问财接口
            df = ak.stock_board_concept_cons_ths(symbol=query)

            if df is None or df.empty:
                return []

            result = []
            for _, row in df.iterrows():
                result.append({
                    "code": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "price": float(row.get("最新价", 0) or 0),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                })

            return result

        except ImportError:
            logger.warning("akshare 未安装")
            return []
        except Exception as e:
            logger.warning(f"akshare 问财搜索失败: {e}")
            raise

    async def _search_with_playwright(self, query: str) -> list[dict]:
        """使用 Playwright 搜索（方案 1 - 推荐）

        通过无头浏览器模拟人类输入，直接抓取渲染后的 DOM 表格。
        """
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                # 启动浏览器
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # 访问问财
                await page.goto("https://www.iwencai.com/")

                # 输入查询
                await page.fill("#search-input", query)
                await page.press("#search-input", "Enter")

                # 等待结果加载
                await page.wait_for_timeout(3000)

                # 提取表格数据
                result = []
                rows = await page.query_selector_all("table tbody tr")

                for row in rows[:20]:  # 限制前 20 行
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 4:
                        code = await cells[0].text_content()
                        name = await cells[1].text_content()
                        price = await cells[2].text_content()
                        change_pct = await cells[3].text_content()

                        result.append({
                            "code": code.strip() if code else "",
                            "name": name.strip() if name else "",
                            "price": float(price) if price else 0,
                            "change_pct": float(change_pct.replace("%", "")) if change_pct else 0,
                        })

                await browser.close()
                return result

        except ImportError:
            logger.warning("Playwright 未安装，请运行: pip install playwright && playwright install chromium")
            return []
        except Exception as e:
            logger.warning(f"Playwright 搜索失败: {e}")
            raise

    async def close(self) -> None:
        """关闭资源"""
        if self._browser:
            await self._browser.close()
            self._browser = None
