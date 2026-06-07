"""基准指数数据源（腾讯财经）

支持的指数：
- 沪深300 (000300)
- 中证500 (000905)
- 中证红利 (000922)
- 创业板指 (399006)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from praxis.core.interfaces import BenchmarkProvider
from praxis.core.models.error import DataError


# 腾讯财经指数代码映射
TENCENT_INDEX_MAP = {
    "000300": "sh000300",  # 沪深300
    "000905": "sh000905",  # 中证500
    "000922": "sh000922",  # 中证红利
    "399006": "sz399006",  # 创业板指
    "000001": "sh000001",  # 上证指数
    "399001": "sz399001",  # 深证成指
}


class TencentBenchmarkProvider(BenchmarkProvider):
    """腾讯财经基准指数数据源"""

    REALTIME_URL = "https://qt.gtimg.cn/q="
    HISTORY_URL = "https://web.ifzq.gtimg.cn/appnew/tech/history"

    def __init__(self, cache_dir: Path | None = None, timeout: float = 10.0):
        self._client = httpx.AsyncClient(timeout=timeout)
        self._cache_dir = cache_dir
        self._memory_cache: dict[str, dict] = {}

    async def get_daily_kline(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """获取日K线数据"""
        # 检查缓存
        cache_key = f"{index_code}_{start_date}_{end_date}"
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        # 从腾讯财经获取
        tencent_code = TENCENT_INDEX_MAP.get(index_code)
        if not tencent_code:
            raise DataError(f"不支持的指数代码: {index_code}", source="tencent")

        try:
            # 计算需要的天数
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            days = (end - start).days + 1

            # 构建请求 URL
            url = f"{self.HISTORY_URL}?param={tencent_code},day,,,{days},qfq"

            resp = await self._client.get(url)
            resp.raise_for_status()
            text = resp.text

            # 解析数据
            kline_data = self._parse_kline(text, start_date, end_date)

            # 更新缓存
            self._memory_cache[cache_key] = kline_data
            if self._cache_dir:
                self._save_cache(cache_key, kline_data)

            return kline_data

        except Exception as e:
            raise DataError(f"获取指数K线失败: {e}", source="tencent")

    def _parse_kline(self, text: str, start_date: str, end_date: str) -> list[dict]:
        """解析腾讯财经K线数据"""
        result = []

        # 格式: v_sh000300_day="20260101,3180.50,3190.20,3200.00,3170.30,123456789"
        match = re.search(r'"(.+)"', text)
        if not match:
            return result

        data_str = match.group(1)
        lines = data_str.split("\\n")

        for line in lines:
            fields = line.split(",")
            if len(fields) >= 6:
                date_str = fields[0]
                # 过滤日期范围
                if start_date.replace("-", "") <= date_str <= end_date.replace("-", ""):
                    result.append({
                        "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
                        "open": float(fields[1]),
                        "close": float(fields[2]),
                        "high": float(fields[3]),
                        "low": float(fields[4]),
                        "volume": int(fields[5]) if fields[5].isdigit() else 0,
                    })

        return result

    async def get_latest_price(self, index_code: str) -> dict:
        """获取最新价格"""
        tencent_code = TENCENT_INDEX_MAP.get(index_code)
        if not tencent_code:
            raise DataError(f"不支持的指数代码: {index_code}", source="tencent")

        try:
            url = f"{self.REALTIME_URL}{tencent_code}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            text = resp.text

            # 解析实时数据
            match = re.search(r'"(.+)"', text)
            if not match:
                raise DataError(f"无法解析指数数据: {index_code}", source="tencent")

            fields = match.group(1).split("~")
            if len(fields) < 45:
                raise DataError(f"指数数据不完整: {index_code}", source="tencent")

            return {
                "code": index_code,
                "name": fields[1],
                "price": float(fields[3]) if fields[3] else 0,
                "prev_close": float(fields[4]) if fields[4] else 0,
                "open": float(fields[5]) if fields[5] else 0,
                "high": float(fields[33]) if fields[33] else 0,
                "low": float(fields[34]) if fields[34] else 0,
                "change": float(fields[31]) if fields[31] else 0,
                "change_pct": float(fields[32]) if fields[32] else 0,
                "volume": int(fields[6]) if fields[6] else 0,
                "date": fields[30][:8] if fields[30] else "",
                "source": "tencent",
            }

        except Exception as e:
            raise DataError(f"获取指数价格失败: {e}", source="tencent")

    def get_supported_indices(self) -> list[dict]:
        """获取支持的指数列表"""
        return [
            {"code": "000300", "name": "沪深300", "description": "大盘价值基准"},
            {"code": "000905", "name": "中证500", "description": "中盘成长基准"},
            {"code": "000922", "name": "中证红利", "description": "红利策略基准"},
            {"code": "399006", "name": "创业板指", "description": "成长风险偏好基准"},
            {"code": "000001", "name": "上证指数", "description": "综合市场基准"},
            {"code": "399001", "name": "深证成指", "description": "深市综合基准"},
        ]

    def _save_cache(self, key: str, data: list[dict]):
        """保存到文件缓存"""
        if not self._cache_dir:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = self._cache_dir / f"benchmark_{key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    async def close(self):
        """关闭 HTTP 客户端"""
        await self._client.aclose()
