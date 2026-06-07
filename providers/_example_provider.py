"""示例数据源插件

复制此文件并修改，即可创建自定义数据源。
文件名不以 _ 开头即可被自动发现。

实现规则：
1. 继承 DataProvider
2. 实现 3 个抽象方法：get_realtime_quote / get_history_kline / get_fund_nav
3. 可选：设置 priority 类属性控制优先级（数字越小优先级越高）
"""
from __future__ import annotations

from praxis.core.interfaces import DataProvider


class ExampleProvider(DataProvider):
    """示例数据源（仅供参考，不会被加载因为是示例）"""

    # 优先级：数字越小越优先
    # 10=AKShare, 20=Baostock, 50=东方财富, 80=腾讯, 90+=用户插件
    priority = 90

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        """获取实时行情

        返回格式:
        {
            "600995": {
                "name": "南网储能",
                "ticker": "600995",
                "price": 15.13,
                "prev_close": 15.65,
                "open": 15.66,
                "volume": 542202,
                "high": 16.48,
                "low": 15.13,
                "change": -0.52,
                "change_pct": -3.32,
                "amount": 85054.0,
                "source": "your_source_name",
            }
        }
        """
        raise NotImplementedError

    async def get_history_kline(
        self, ticker: str, period: str = "day", count: int = 60
    ) -> list[dict]:
        """获取历史K线

        返回格式:
        [
            {
                "date": "2026-06-05",
                "open": 15.66,
                "close": 15.13,
                "high": 16.48,
                "low": 15.13,
                "volume": 542202,
                "amount": 85054.0,
                "change_pct": -3.32,
                "source": "your_source_name",
            }
        ]
        """
        raise NotImplementedError

    async def get_fund_nav(self, ticker: str) -> dict:
        """获取基金净值

        返回格式:
        {
            "ticker": "016874",
            "name": "广发远见智选C",
            "nav": 1.9456,
            "acc_nav": 1.9456,
            "nav_date": "2026-06-05",
            "change_pct": -3.01,
            "source": "your_source_name",
        }
        """
        raise NotImplementedError

    async def close(self):
        """关闭连接（如有持久连接）"""
        pass
