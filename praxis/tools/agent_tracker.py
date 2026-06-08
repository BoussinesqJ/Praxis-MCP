"""MCP 工具 - 多 Agent 协作"""
from __future__ import annotations

from datetime import datetime

from praxis.engine.consensus import AgentDecision, AgentDecisionStore, ConsensusEngine


def record_agent_decision(
    agent_id: str,
    ticker: str,
    action: str,
    confidence: float,
    reasoning: str,
    price_target: float | None = None,
    stop_loss: float | None = None,
    time_horizon: str = "short",
    source_team: str = "",
    workspace: str = ".",
) -> dict:
    """记录 Agent 决策（标准化接口）"""
    try:
        store = AgentDecisionStore(workspace)
        decision = AgentDecision(
            decision_id=f"agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            agent_id=agent_id,
            timestamp=datetime.now().isoformat(),
            ticker=ticker,
            action=action,
            confidence=confidence,
            reasoning=reasoning,
            price_target=price_target,
            stop_loss=stop_loss,
            time_horizon=time_horizon,
            source_team=source_team,
        )
        decision_id = store.record(decision)
        return {
            "success": True,
            "data": {"decision_id": decision_id, "message": f"Agent {agent_id} 决策已记录"},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_consensus(
    ticker: str,
    min_agents: int = 2,
    workspace: str = ".",
) -> dict:
    """检查多 Agent 共识"""
    try:
        store = AgentDecisionStore(workspace)
        engine = ConsensusEngine(store)
        result = engine.check_consensus(ticker, min_agents=min_agents)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def rank_agents(workspace: str = ".") -> dict:
    """排名所有 Agent"""
    try:
        store = AgentDecisionStore(workspace)
        engine = ConsensusEngine(store)
        rankings = engine.rank_agents()
        return {
            "success": True,
            "data": {
                "total_agents": len(rankings),
                "rankings": rankings,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
