"""MCP 工具 - 数据质量检查

GPT 要求：增加 Data Quality Layer，确保输入数据可靠。
"""
from __future__ import annotations

from praxis.engine.data_quality import DataQualityChecker, DataQualityMonitor


def check_quote_quality(
    ticker: str,
    data: dict,
    workspace: str = ".",
) -> dict:
    """检查行情数据质量

    Args:
        ticker: 标的代码
        data: 行情数据

    Returns:
        质量检查结果
    """
    try:
        checker = DataQualityChecker()
        is_valid, errors = checker.validate_quote(ticker, data)
        return {
            "success": True,
            "data": {
                "ticker": ticker,
                "is_valid": is_valid,
                "errors": errors,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def clean_quote_data(
    ticker: str,
    data: dict,
    workspace: str = ".",
) -> dict:
    """清洗行情数据

    Args:
        ticker: 标的代码
        data: 原始行情数据

    Returns:
        清洗后的数据
    """
    try:
        checker = DataQualityChecker()
        cleaned = checker.clean_quote(ticker, data)
        return {
            "success": True,
            "data": cleaned,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_quality_report(
    workspace: str = ".",
) -> dict:
    """获取数据质量报告

    Returns:
        质量报告
    """
    try:
        monitor = DataQualityMonitor()
        report = monitor.get_quality_report()
        return {
            "success": True,
            "data": report,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
