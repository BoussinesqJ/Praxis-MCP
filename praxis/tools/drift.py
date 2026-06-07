"""MCP 工具 - 漂移检测与账本审计"""
from __future__ import annotations

from pathlib import Path
from praxis.core.ledger import FileLedger
from praxis.core.database import Database
from praxis.engine.decision_recorder import FileDecisionRecorder
from praxis.engine.drift_detector import AIDriftDetector


def verify_ledger_integrity(workspace: str = ".") -> dict:
    """审计检查交易账本的 SHA-256 链接及哈希完整性"""
    try:
        db = Database(Path(workspace) / "data" / "praxis_system.db")
        ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
        ledger = FileLedger(ledger_path, db=db)
        passed, errors = ledger.verify_integrity()
        return {
            "success": True,
            "data": {
                "passed": passed,
                "errors": errors,
                "total_transactions": ledger.count(),
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def detect_ai_drift(team_name: str | None = None, workspace: str = ".") -> dict:
    """计算 AI 决策的 ECE 和 Brier score 标定性，并给出风控预警状态"""
    try:
        decisions_path = Path(workspace) / "data" / "decisions" / "decision_records.jsonl"
        recorder = FileDecisionRecorder(decisions_path)
        decisions = recorder.get_all()

        detector = AIDriftDetector()
        res = detector.detect_drift(decisions, team_name=team_name)

        return {
            "success": True,
            "data": res.model_dump(mode="json"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
