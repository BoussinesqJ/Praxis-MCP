"""
Praxis v3.0 断点续传模块（Checkpoint Recovery）

借鉴 TradingAgents 的检查点思路，采用 JSON 方案（白盒可读）替代 SQLite。
解决 three-team 因意外中断导致 80K token 全部浪费的痛点。

设计原则：
- 断点粒度：按子 Agent 阶段（ASRG / Masters / Trading Phase 1-4）
- 存储内容：完整 Markdown 输出（Full Text）
- 过期策略：严格绑定 trade_date，隔日自动失效
- 回滚机制：PRAXIS_CHECKPOINT_ENABLED 环境变量控制
- 存储位置：outputs/checkpoints/{ticker}-{date}.json
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


# Feature flag: 环境变量控制，默认启用
CHECKPOINT_ENABLED = os.environ.get("PRAXIS_CHECKPOINT_ENABLED", "true").lower() in ("true", "1", "yes")

# 断点存储目录
CHECKPOINT_DIR = Path(__file__).parent.parent.parent / "outputs" / "checkpoints"

# 合法的阶段标识
VALID_PHASES = {
    "asrg",           # ASRG 战术研究完成
    "masters",        # Masters 大师圆桌完成
    "trading_p1",     # Trading Phase 1 数据收集完成
    "trading_p2",     # Trading Phase 2 多空辩论完成
    "trading_p3",     # Trading Phase 3 交易员方案完成
    "trading_p4",     # Trading Phase 4 风险评估完成
}


def _checkpoint_path(ticker: str, trade_date: str) -> Path:
    """生成断点文件路径。ticker 做安全过滤防止路径遍历。"""
    # 过滤掉所有非字母数字和分隔符的字符，特别处理 .. 路径遍历
    safe_ticker = "".join(c for c in ticker if c.isalnum() or c in "-_.")
    # 再次去除连续的点号（防止 ../.. 等路径遍历）
    while ".." in safe_ticker:
        safe_ticker = safe_ticker.replace("..", "")
    return CHECKPOINT_DIR / f"{safe_ticker}-{trade_date}.json"


def save_checkpoint(
    ticker: str,
    trade_date: str,
    phase: str,
    data: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """保存断点。

    Args:
        ticker: 标的代码（如 "000001"）
        trade_date: 交易日期（如 "2026-06-12"）
        phase: 完成的阶段标识（必须在 VALID_PHASES 中）
        data: 该阶段的完整 Markdown 输出
        metadata: 可选元数据（如 token 消耗、耗时等）

    Returns:
        True if saved successfully, False if disabled or error
    """
    if not CHECKPOINT_ENABLED:
        return False

    if phase not in VALID_PHASES:
        raise ValueError(f"Invalid phase '{phase}'. Must be one of: {VALID_PHASES}")

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = _checkpoint_path(ticker, trade_date)

    # 读取已有断点（如果有），追加新阶段
    existing = load_checkpoint_raw(ticker, trade_date) or {
        "ticker": ticker,
        "trade_date": trade_date,
        "created_at": datetime.now().isoformat(),
        "phases": {},
    }

    existing["phases"][phase] = {
        "data": data,
        "saved_at": datetime.now().isoformat(),
        "metadata": metadata or {},
    }
    existing["updated_at"] = datetime.now().isoformat()

    # 原子写入：先写临时文件再 rename
    tmp_path = path.with_suffix(".json.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        tmp_path.replace(path)
        return True
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        return False


def load_checkpoint(ticker: str, trade_date: str) -> Optional[Dict[str, str]]:
    """加载断点，返回已完成阶段的字典 {phase: markdown_data}。

    如果断点不存在、已过期（trade_date 不匹配）、或功能被禁用，返回 None。
    """
    if not CHECKPOINT_ENABLED:
        return None

    raw = load_checkpoint_raw(ticker, trade_date)
    if raw is None:
        return None

    # 过期检查：严格绑定 trade_date
    if raw.get("trade_date") != trade_date:
        return None

    # 返回 {phase: data} 字典
    return {phase: info["data"] for phase, info in raw.get("phases", {}).items()}


def load_checkpoint_raw(ticker: str, trade_date: str) -> Optional[Dict]:
    """加载断点原始 JSON 数据（含元数据）。"""
    path = _checkpoint_path(ticker, trade_date)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def clear_checkpoint(ticker: str, trade_date: str) -> bool:
    """清除指定断点（分析成功完成后调用）。"""
    path = _checkpoint_path(ticker, trade_date)
    if path.exists():
        path.unlink()
        return True
    return False


def clear_all_checkpoints() -> int:
    """清除所有断点。返回删除的文件数。"""
    if not CHECKPOINT_DIR.exists():
        return 0
    count = 0
    for f in CHECKPOINT_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count


def get_checkpoint_summary(ticker: str, trade_date: str) -> Optional[str]:
    """返回断点的人类可读摘要（用于日志输出）。"""
    raw = load_checkpoint_raw(ticker, trade_date)
    if raw is None:
        return None

    phases = raw.get("phases", {})
    completed = list(phases.keys())
    next_phase = _next_phase(completed)

    return (
        f"Resuming {ticker} on {trade_date}: "
        f"completed {len(completed)}/{len(VALID_PHASES)} phases "
        f"({', '.join(completed)}). "
        f"Next: {next_phase or 'all done'}"
    )


def _next_phase(completed_phases: list) -> Optional[str]:
    """按顺序返回下一个待执行的阶段。"""
    ordered = ["asrg", "masters", "trading_p1", "trading_p2", "trading_p3", "trading_p4"]
    for phase in ordered:
        if phase not in completed_phases:
            return phase
    return None
