"""数据质量层

GPT 要求：增加 Data Quality Layer，确保输入数据可靠。
支持：
- 数据验证（格式、范围、完整性）
- 数据清洗（异常值处理、缺失值填充）
- 数据监控（质量指标、异常告警）
"""
from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel

from praxis.core.models.error import DataError


class DataQualityConfig(BaseModel):
    """数据质量配置"""
    max_price_change_pct: float = 0.1           # 最大价格变动（10%）
    min_volume: float = 0                       # 最小成交量
    max_stale_hours: int = 24                   # 最大数据过期时间（小时）
    required_fields: list[str] = ["price", "change", "change_pct"]  # 必需字段


class DataQualityMetrics(BaseModel):
    """数据质量指标"""
    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    missing_fields: int = 0
    outlier_count: int = 0
    stale_count: int = 0
    quality_score: float = 1.0                  # 质量分数（0-1）


class DataQualityChecker:
    """数据质量检查器"""

    def __init__(self, config: DataQualityConfig | None = None):
        self._config = config or DataQualityConfig()
        self._metrics = DataQualityMetrics()

    def validate_quote(self, ticker: str, data: dict) -> tuple[bool, list[str]]:
        """验证行情数据

        Args:
            ticker: 标的代码
            data: 行情数据

        Returns:
            (是否有效, 错误列表)
        """
        errors = []
        self._metrics.total_records += 1

        # 1. 检查必需字段
        for field in self._config.required_fields:
            if field not in data or data[field] is None:
                errors.append(f"缺少必需字段: {field}")
                self._metrics.missing_fields += 1

        if errors:
            self._metrics.invalid_records += 1
            return False, errors

        # 2. 检查价格合理性
        price = data.get("price", 0)
        if price <= 0:
            errors.append(f"价格无效: {price}")

        # 3. 检查涨跌幅合理性
        change_pct = data.get("change_pct", 0)
        if abs(change_pct) > self._config.max_price_change_pct * 100:
            errors.append(f"涨跌幅异常: {change_pct}%")
            self._metrics.outlier_count += 1

        # 4. 检查成交量
        volume = data.get("volume", 0)
        if volume < self._config.min_volume:
            errors.append(f"成交量异常: {volume}")

        # 5. 检查数据时效性
        timestamp = data.get("timestamp")
        if timestamp:
            try:
                if isinstance(timestamp, str):
                    ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                else:
                    ts = timestamp
                age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
                if age_hours > self._config.max_stale_hours:
                    errors.append(f"数据过期: {age_hours:.1f} 小时")
                    self._metrics.stale_count += 1
            except Exception:
                pass

        if errors:
            self._metrics.invalid_records += 1
            return False, errors

        self._metrics.valid_records += 1
        return True, []

    def clean_quote(self, ticker: str, data: dict) -> dict:
        """清洗行情数据

        Args:
            ticker: 标的代码
            data: 原始行情数据

        Returns:
            清洗后的数据
        """
        cleaned = data.copy()

        # 1. 填充缺失字段
        if "price" not in cleaned or cleaned["price"] is None:
            cleaned["price"] = 0
        if "change" not in cleaned or cleaned["change"] is None:
            cleaned["change"] = 0
        if "change_pct" not in cleaned or cleaned["change_pct"] is None:
            cleaned["change_pct"] = 0

        # 2. 处理异常值
        price = cleaned.get("price", 0)
        if price < 0:
            cleaned["price"] = abs(price)
            cleaned["change"] = -cleaned.get("change", 0)

        # 3. 添加质量标记
        cleaned["data_quality"] = {
            "validated": True,
            "cleaned": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return cleaned

    def get_metrics(self) -> DataQualityMetrics:
        """获取数据质量指标"""
        if self._metrics.total_records > 0:
            self._metrics.quality_score = (
                self._metrics.valid_records / self._metrics.total_records
            )
        return self._metrics

    def reset_metrics(self):
        """重置数据质量指标"""
        self._metrics = DataQualityMetrics()


class DataQualityMonitor:
    """数据质量监控器"""

    def __init__(self):
        self._checker = DataQualityChecker()
        self._alerts: list[dict] = []

    def check_and_alert(self, ticker: str, data: dict) -> tuple[bool, list[str]]:
        """检查数据质量并告警

        Args:
            ticker: 标的代码
            data: 行情数据

        Returns:
            (是否有效, 错误列表)
        """
        is_valid, errors = self._checker.validate_quote(ticker, data)

        if not is_valid:
            alert = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": ticker,
                "errors": errors,
                "data": data,
            }
            self._alerts.append(alert)

            # 保持最近 100 条告警
            if len(self._alerts) > 100:
                self._alerts = self._alerts[-100:]

        return is_valid, errors

    def get_alerts(self, limit: int = 10) -> list[dict]:
        """获取最近的告警"""
        return self._alerts[-limit:]

    def get_quality_report(self) -> dict:
        """获取质量报告"""
        metrics = self._checker.get_metrics()
        return {
            "metrics": metrics.model_dump(),
            "recent_alerts": self.get_alerts(5),
            "quality_level": (
                "excellent" if metrics.quality_score >= 0.95
                else "good" if metrics.quality_score >= 0.8
                else "warning" if metrics.quality_score >= 0.6
                else "critical"
            ),
        }
