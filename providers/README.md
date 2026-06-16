# Praxis 数据源插件开发指南

## 快速开始

1. 在 `providers/` 目录创建 Python 文件（如 `my_provider.py`）
2. 实现 `DataProvider` 接口
3. 重启 Praxis，插件自动加载

## 最小示例

```python
# providers/my_provider.py
from praxis.core.interfaces import DataProvider

class MyProvider(DataProvider):
    priority = 30  # 数字越小越优先

    async def get_realtime_quote(self, tickers: list[str]) -> dict[str, dict]:
        # 返回 {ticker: {name, price, volume, ...}}
        ...

    async def get_history_kline(self, ticker: str, period: str, count: int) -> list[dict]:
        # 返回 [{date, open, close, high, low, volume}]
        ...

    async def get_fund_nav(self, ticker: str) -> dict:
        # 返回 {ticker, nav, nav_date, ...}
        ...

    async def close(self):
        pass
```

## 优先级参考

| 优先级 | 数据源 | 说明 |
|---|---|---|
| 10 | AKShare | 需 `pip install akshare` |
| 20 | Baostock | 需 `pip install baostock` |
| 50 | 东方财富 | 内置，零依赖 |
| 80 | 腾讯 | 内置，零依赖 |
| 90+ | 用户插件 | 建议 90 起 |

## 配置覆盖

在 `config/data_sources.yaml` 中可覆盖优先级和启用状态：

```yaml
providers:
  my_provider:
    enabled: true
    priority: 15
```

## 调试

插件加载失败会在日志中记录警告，不会影响系统启动。
查看日志：`data/logs/praxis.log`
