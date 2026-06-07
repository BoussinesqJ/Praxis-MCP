"""PRAXIS 统一日志系统

提供统一的日志记录功能，支持：
- 控制台输出
- 文件记录
- 日志级别控制
- 结构化日志
"""
from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class PraxisLogger:
    """PRAXIS 日志记录器"""

    def __init__(
        self,
        name: str = "praxis",
        log_dir: str | Path | None = None,
        level: int = logging.INFO,
    ):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        # 避免重复添加处理器
        if not self._logger.handlers:
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self._logger.addHandler(console_handler)

            # 文件处理器（如果指定了日志目录）
            if log_dir:
                log_path = Path(log_dir)
                log_path.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(
                    log_path / "praxis.log",
                    encoding="utf-8",
                )
                file_handler.setLevel(level)
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                self._logger.addHandler(file_handler)

    def info(self, message: str, **kwargs: Any) -> None:
        """记录信息日志"""
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """记录警告日志"""
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """记录错误日志"""
        self._logger.error(message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """记录调试日志"""
        self._logger.debug(message, **kwargs)

    def tool_call(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        success: bool,
        duration_ms: int,
        error: str | None = None,
    ) -> None:
        """记录 MCP 工具调用"""
        log_data = {
            "event": "tool_call",
            "tool": tool_name,
            "parameters": parameters,
            "success": success,
            "duration_ms": duration_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if error:
            log_data["error"] = error

        if success:
            self._logger.info(f"工具调用: {tool_name} ({duration_ms}ms)")
        else:
            self._logger.error(f"工具调用失败: {tool_name} - {error}")

    def decision(
        self,
        decision_id: str,
        ticker: str,
        action: str,
        confidence: float,
    ) -> None:
        """记录决策"""
        self._logger.info(
            f"决策记录: {decision_id} {action} {ticker} 信心度={confidence:.2f}"
        )

    def transaction(
        self,
        tx_id: str,
        action: str,
        ticker: str,
        quantity: float,
        price: float,
    ) -> None:
        """记录交易"""
        self._logger.info(
            f"交易记录: {tx_id} {action} {ticker} {quantity}@{price}"
        )

    def review(
        self,
        decision_id: str,
        review_type: str,
        actual_return: float | None,
    ) -> None:
        """记录复盘"""
        if actual_return is not None:
            self._logger.info(
                f"复盘记录: {decision_id} {review_type} 收益={actual_return:.2%}"
            )
        else:
            self._logger.info(f"复盘记录: {decision_id} {review_type} 收益=N/A")


# 全局日志实例
_logger: PraxisLogger | None = None


def get_logger() -> PraxisLogger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        _logger = PraxisLogger()
    return _logger


def init_logger(log_dir: str | Path | None = None, level: int = logging.INFO) -> PraxisLogger:
    """初始化日志系统"""
    global _logger
    _logger = PraxisLogger(log_dir=log_dir, level=level)
    return _logger
