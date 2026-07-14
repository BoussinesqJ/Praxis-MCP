"""PRAXIS 统一日志框架 — 基于 structlog

日志级别规范:
    DEBUG    — 开发调试
    INFO     — 正常流程
    WARNING  — 可恢复异常
    ERROR    — 需关注
    CRITICAL — 需立即处理
"""

from __future__ import annotations

import logging
import os
import sys
import structlog


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: str | None = None,
) -> None:
    """初始化全局日志配置

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        json_format: 是否使用 JSON 行格式（生产环境推荐）
        log_file: 日志文件路径（可选）
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 配置标准库 logging（作为 structlog 的后端）
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=handlers,
    )

    # 抑制第三方库噪音
    for noisy in ["httpx", "httpcore", "urllib3", "akshare", "ak", "matplotlib"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # 配置 structlog
    processors: list = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取结构化日志记录器

    Usage:
        logger = get_logger(__name__)
        logger.info("tool_called", tool_name="sentinel", action="scan")
        logger.error("data_fetch_failed", ticker="000001", error=str(e))
    """
    return structlog.get_logger(name)


# 默认初始化（安全级别+控制台输出）
_default_level = os.environ.get("PRAXIS_LOG_LEVEL", "INFO")
_default_json = os.environ.get("PRAXIS_LOG_JSON", "true").lower() == "true"

setup_logging(level=_default_level, json_format=_default_json)
