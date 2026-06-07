"""MCP 工具 - 复盘管理"""
from __future__ import annotations

import asyncio
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.engine.data.provider import CachedDataProvider
from praxis.engine.review_filler import ReviewFiller


def _get_filler(workspace: str = ".") -> ReviewFiller:
    """获取复盘填充器实例"""
    decisions_path = Path(workspace) / "data" / "decisions" / "decision_records.jsonl"
    ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
    recorder = FileDecisionRecorder(decisions_path)
    ledger = FileLedger(ledger_path)
    provider = CachedDataProvider()
    return ReviewFiller(recorder, ledger, provider)


async def fill_reviews(workspace: str = ".") -> dict:
    """自动回填待复盘的决策"""
    filler = _get_filler(workspace)
    try:
        results = await filler.fill_pending_reviews()
        summary = filler.get_summary()
        return {
            "success": True,
            "data": {
                "filled": results,
                "summary": {
                    "total_decisions": summary.total_decisions,
                    "pending_5d": summary.pending_5d,
                    "pending_20d": summary.pending_20d,
                    "pending_60d": summary.pending_60d,
                    "filled_count": summary.filled_count,
                },
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_review_summary(workspace: str = ".") -> dict:
    """获取复盘汇总"""
    try:
        filler = _get_filler(workspace)
        summary = filler.get_summary()
        return {
            "success": True,
            "data": {
                "total_decisions": summary.total_decisions,
                "pending_5d": summary.pending_5d,
                "pending_20d": summary.pending_20d,
                "pending_60d": summary.pending_60d,
                "filled_count": summary.filled_count,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_confidence_calibration(team: str, workspace: str = ".") -> dict:
    """获取指定团队的信心度校准"""
    try:
        filler = _get_filler(workspace)
        result = filler.calculate_confidence_calibration(team)
        return {
            "success": True,
            "data": result,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
