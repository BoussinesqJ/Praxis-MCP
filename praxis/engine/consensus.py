"""多 Agent 共识引擎

标准化不同 AI Agent 的分析结果，比较建议质量，检查共识。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger("praxis.consensus")


class AgentDecision(BaseModel):
    """标准化 Agent 决策记录"""
    decision_id: str
    agent_id: str           # reasonix / gemini / claude
    timestamp: str
    ticker: str
    action: str             # buy / sell / hold / watch
    confidence: float       # 0.0 - 1.0
    reasoning: str
    price_target: float | None = None
    stop_loss: float | None = None
    time_horizon: str = "short"  # short / medium / long
    source_team: str = ""   # asrg / masters / trading


class AgentDecisionStore:
    """Agent 决策存储"""

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._decisions_dir = self._workspace / "data" / "agent_decisions"
        self._decisions_dir.mkdir(parents=True, exist_ok=True)

    def record(self, decision: AgentDecision) -> str:
        """记录 Agent 决策"""
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
                line = line.strip()
                if not line:
                    continue
                try:
                    decisions.append(AgentDecision(**json.loads(line)))
                except Exception:
                    continue
        return decisions[-limit:]

    def load_ticker_decisions(self, ticker: str, limit: int = 50) -> list[AgentDecision]:
        """加载某标的的所有 Agent 决策"""
        decisions = []
        for f in self._decisions_dir.glob("*.jsonl"):
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = AgentDecision(**json.loads(line))
                        if d.ticker == ticker:
                            decisions.append(d)
                    except Exception:
                        continue
        return sorted(decisions, key=lambda d: d.timestamp, reverse=True)[:limit]


class ConsensusEngine:
    """多 Agent 共识引擎"""

    def __init__(self, store: AgentDecisionStore):
        self._store = store

    def check_consensus(
        self,
        ticker: str,
        decisions: list[AgentDecision] | None = None,
        min_agents: int = 2,
    ) -> dict:
        """检查多 Agent 共识"""
        if decisions is None:
            decisions = self._store.load_ticker_decisions(ticker)

        if not decisions:
            return {
                "ticker": ticker,
                "consensus": False,
                "recommended_action": None,
                "vote_distribution": {},
                "total_agents": 0,
                "consensus_ratio": 0,
                "message": f"标的 {ticker} 暂无 Agent 决策记录",
            }

        # 去重：每个 Agent 只取最新一条
        latest_by_agent: dict[str, AgentDecision] = {}
        for d in decisions:
            if d.agent_id not in latest_by_agent or d.timestamp > latest_by_agent[d.agent_id].timestamp:
                latest_by_agent[d.agent_id] = d

        unique_decisions = list(latest_by_agent.values())

        # 统计 action 分布
        action_counts: dict[str, int] = {}
        for d in unique_decisions:
            action_counts[d.action] = action_counts.get(d.action, 0) + 1

        # 找到最高票 action
        top_action = max(action_counts, key=action_counts.get)
        top_count = action_counts[top_action]
        total = len(unique_decisions)

        consensus = top_count >= min_agents

        return {
            "ticker": ticker,
            "consensus": consensus,
            "recommended_action": top_action if consensus else None,
            "vote_distribution": action_counts,
            "total_agents": total,
            "consensus_ratio": round(top_count / total, 2) if total > 0 else 0,
            "agents": [
                {"agent_id": d.agent_id, "action": d.action, "confidence": d.confidence}
                for d in unique_decisions
            ],
            "message": (
                f"{'达成共识' if consensus else '未达共识'}: "
                f"{top_action} ({top_count}/{total} agents)"
            ),
        }

    def rank_agents(self) -> list[dict]:
        """排名所有 Agent（按决策数量和平均置信度）"""
        agent_stats: dict[str, dict] = {}

        for f in self._store._decisions_dir.glob("*.jsonl"):
            agent_id = f.stem
            decisions = self._store.load_agent_decisions(agent_id)
            if not decisions:
                continue

            avg_confidence = sum(d.confidence for d in decisions) / len(decisions)
            action_dist: dict[str, int] = {}
            for d in decisions:
                action_dist[d.action] = action_dist.get(d.action, 0) + 1

            agent_stats[agent_id] = {
                "agent_id": agent_id,
                "total_decisions": len(decisions),
                "avg_confidence": round(avg_confidence, 3),
                "action_distribution": action_dist,
            }

        # 按决策数量排序
        ranked = sorted(agent_stats.values(), key=lambda x: x["total_decisions"], reverse=True)
        for i, agent in enumerate(ranked):
            agent["rank"] = i + 1

        return ranked
