"""Agent追踪 — agent_tracking"""
from __future__ import annotations
from praxis.agents.base import Tool
from praxis.tools._schemas import AgentTrackingInput
from praxis.engine.consensus import AgentDecision, AgentDecisionStore, ConsensusEngine

async def agent_tracking(action: str, agent_id: str | None = None, ticker: str | None = None,
                         decision_action: str | None = None, confidence: float | None = None,
                         reasoning: str | None = None, min_agents: int = 2,
                         _deps: dict | None = None) -> dict:
    store = AgentDecisionStore(_deps.get("workspace", ".") if _deps else ".")
    if action == "record":
        if not all([agent_id, ticker, decision_action, confidence, reasoning]):
            return {"success": False, "error": "缺少必填参数"}
        import uuid
        d = AgentDecision(agent_id=agent_id, ticker=ticker, action=decision_action,
                          confidence=confidence, reasoning=reasoning,
                          decision_id=f"agent-dec-{uuid.uuid4().hex[:12]}")
        store.record(d)
        return {"success": True, "data": {"decision_id": d.decision_id}}
    elif action == "consensus":
        if not ticker:
            return {"success": False, "error": "需要 ticker"}
        engine = ConsensusEngine(store)
        return engine.check_consensus(ticker, min_agents)
    elif action == "rank":
        engine = ConsensusEngine(store)
        return {"success": True, "data": engine.rank_agents()}
    return {"success": False, "error": f"未知 action: {action}"}

def register(registry):
    registry.register(Tool(name="agent_tracking", description="Agent决策追踪：record/consensus/rank",
                           input_schema=AgentTrackingInput, handler=agent_tracking, agent_name="review", tier="core"))
