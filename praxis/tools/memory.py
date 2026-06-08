"""MCP 工具 - 进化记忆"""
from __future__ import annotations

from praxis.engine.evolution_memory import EvolutionMemoryStore


def record_evolution_memory(
    trigger_event: str,
    strategy_name: str,
    evaluation_summary: str,
    dimensions: list[dict] | None = None,
    suggestions: list[dict] | None = None,
    workspace: str = ".",
) -> dict:
    """记录一次进化记忆"""
    try:
        store = EvolutionMemoryStore(workspace)
        path = store.record(
            trigger_event=trigger_event,
            strategy_name=strategy_name,
            evaluation_summary=evaluation_summary,
            dimensions=dimensions,
            suggestions=suggestions,
        )
        return {
            "success": True,
            "data": {"path": path, "message": "进化记忆已记录"},
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_evolution_timeline(strategy_name: str, workspace: str = ".") -> dict:
    """获取策略进化时间线"""
    try:
        store = EvolutionMemoryStore(workspace)
        timeline = store.generate_timeline(strategy_name)
        memories = store.load_all()
        strategy_memories = [m for m in memories if m.strategy_name == strategy_name]

        return {
            "success": True,
            "data": {
                "strategy_name": strategy_name,
                "timeline": timeline,
                "total_records": len(strategy_memories),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def query_evolution_memory(situation: str, limit: int = 5, workspace: str = ".") -> dict:
    """查询类似情况的历史进化记录"""
    try:
        store = EvolutionMemoryStore(workspace)
        memories = store.query_similar(situation, limit)

        return {
            "success": True,
            "data": {
                "query": situation,
                "results_count": len(memories),
                "results": [m.model_dump() for m in memories],
                "message": f"找到 {len(memories)} 条类似记录" if memories else "未找到类似记录",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
