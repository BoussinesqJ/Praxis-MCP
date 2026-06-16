"""数据质量工具测试"""
import pytest
from praxis.tools.data_quality import (
    check_quote_quality,
    clean_quote_data,
    get_quality_report,
)


class TestCheckQuoteQuality:
    """行情数据质量检查测试"""

    def test_valid_quote(self):
        """有效行情数据"""
        quote = {
            "ticker": "000001",
            "close": 13.50,
            "open": 13.40,
            "high": 13.60,
            "low": 13.30,
            "volume": 1000000,
            "date": "2026-06-05",
            "price": 13.50,
            "change": 0.10,
            "change_pct": 0.75,
        }
        result = check_quote_quality(ticker="000001", data=quote)
        assert result["success"] is True
        assert result["data"]["is_valid"] is True

    def test_missing_fields(self):
        """缺少字段的行情数据"""
        quote = {
            "ticker": "000001",
            "close": 13.50,
        }
        result = check_quote_quality(ticker="000001", data=quote)
        assert result["success"] is True
        # 缺少字段会导致验证失败
        assert result["data"]["is_valid"] is False

    def test_invalid_price(self):
        """无效价格"""
        quote = {
            "ticker": "000001",
            "close": -1.0,
            "open": 13.40,
            "high": 13.60,
            "low": 13.30,
            "volume": 1000000,
            "date": "2026-06-05",
        }
        result = check_quote_quality(ticker="000001", data=quote)
        assert result["success"] is True
        # 无效价格会导致验证失败
        assert result["data"]["is_valid"] is False


class TestCleanQuoteData:
    """行情数据清洗测试"""

    def test_clean_valid_data(self):
        """清洗有效数据"""
        quote = {
            "ticker": "000001",
            "close": 13.50,
            "open": 13.40,
            "high": 13.60,
            "low": 13.30,
            "volume": 1000000,
            "date": "2026-06-05",
        }
        result = clean_quote_data(ticker="000001", data=quote)
        assert result["success"] is True
        assert result["data"] is not None

    def test_clean_with_outliers(self):
        """清洗包含异常值的数据"""
        quote = {
            "ticker": "000001",
            "close": 13.50,
            "open": 13.40,
            "high": 100.0,  # 异常高值
            "low": 13.30,
            "volume": 1000000,
            "date": "2026-06-05",
        }
        result = clean_quote_data(ticker="000001", data=quote)
        assert result["success"] is True


class TestGetQualityReport:
    """质量报告测试"""

    def test_get_report(self):
        """获取质量报告"""
        result = get_quality_report()
        assert result["success"] is True
        assert "metrics" in result["data"]
