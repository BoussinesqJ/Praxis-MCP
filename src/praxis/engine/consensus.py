"""多 Agent 共识引擎 — 标准化 Agent 决策 + 共识检查 + 排名"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from pydantic import BaseModel

from praxis.core.logging_config import get_logger

logger = get_logger(__name__)


class AgentDecision(BaseModel):
    """标准化 Agent 决策记录"""
    decision_id: str = ""
    agent_id: str
    timestamp: str = ""
    ticker: str
    action: str  # buy / sell / hold / watch
    confidence: float  # 0.0 - 1.0
    reasoning: str = ""
    price_target: float | None = None
    stop_loss: float | None = None
    time_horizon: str = "short"
    source_team: str = ""


class AgentDecisionStore:
    """Agent 决策存储（JSONL）"""

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._decisions_dir = self._workspace / "data" / "agent_decisions"
        self._decisions_dir.mkdir(parents=True, exist_ok=True)

    def record(self, decision: AgentDecision) -> str:
        """记录 Agent 决策，返回 decision_id"""
        if not decision.decision_id:
            decision.decision_id = f"agent-dec-{uuid.uuid4().hex[:12]}"
        path = self._decisions_dir / f"{decision.agent_id}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(decision.model_dump_json() + "\n")
        return decision.decision_id

    def load_agent_decisions(self, agent_id: str, limit: int = 100) -> list[AgentDecision]:
        """加载某 Agent 的决策记录"""
        path = self._decisions_dir / f"{agent_id}.jsonl"
        if not path.exists():
            return []
        decisions = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    decisions.append(AgentDecision(**json.loads(line.strip())))
                except Exception:
                    continue
        return decisions[-limit:]


class ConsensusEngine:
    """多 Agent 共识引擎"""

    def __init__(self, store: AgentDecisionStore):
        self._store = store

    def check_consensus(self, ticker: str, min_agents: int = 2) -> dict:
        """检查多 Agent 是否达成共识"""
        all_agents = ["reasonix", "gemini", "claude"]
        actions = []

        for agent_id in all_agents:
            decisions = self._store.load_agent_decisions(agent_id, limit=10)
            ticker_decisions = [d for d in decisions if d.ticker == ticker]
            if ticker_decisions:
                latest = ticker_decisions[-1]
                actions.append({"agent_id": agent_id, "action": latest.action,
                                "confidence": latest.confidence})

        if len(actions) < min_agents:
            return {"consensus_reached": False, "reason": f"参与Agent不足 ({len(actions)}/{min_agents})",
                    "actions": actions}

        # 统计 action 分布
        action_counts = {}
        for a in actions:
            action_counts[a["action"]] = action_counts.get(a["action"], 0) + 1

        max_count = max(action_counts.values()) if action_counts else 0
        consensus = max_count >= min_agents

        return {
            "consensus_reached": consensus,
            "reason": f"{max_count}/{len(actions)} Agent 达成一致" if consensus else "未达成共识",
            "actions": actions,
            "action_distribution": action_counts,
        }

    def rank_agents(self) -> list[dict]:
        """排名所有 Agent（按决策数量+平均置信度）"""
        all_agents = ["reasonix", "gemini", "claude"]
        rankings = []

        for agent_id in all_agents:
            decisions = self._store.load_agent_decisions(agent_id)
            if not decisions:
                rankings.append({"agent_id": agent_id, "total_decisions": 0,
                                 "avg_confidence": 0, "score": 0})
                continue

            avg_conf = sum(d.confidence for d in decisions) / len(decisions)
            score = len(decisions) * avg_conf
            rankings.append({"agent_id": agent_id, "total_decisions": len(decisions),
                             "avg_confidence": round(avg_conf, 4), "score": round(score, 2)})

        rankings.sort(key=lambda x: x["score"], reverse=True)
        return rankings
