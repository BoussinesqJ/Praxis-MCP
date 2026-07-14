"""记忆检索工具 — memory_search

语义检索历史决策、复盘报告、研报摘要。
支持多集合检索，结果按相似度排序。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from praxis.agents.base import Tool


class MemorySearchInput(BaseModel):
    query: str = Field(..., description="搜索查询文本")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数")
    collection: str = Field(default="all", description="集合: all/decisions/reviews/research")
    min_score: float = Field(default=0.15, ge=0.0, le=1.0, description="最低相似度阈值")


async def memory_search(query: str, top_k: int = 5, collection: str = "all",
                        min_score: float = 0.3, _deps: dict | None = None) -> dict:
    """语义检索历史记忆"""
    store = _deps.get("memory_store") if _deps else None
    if store is None:
        return {"success": False, "error": "MemoryStore 未注入。请确保 PRAXIS_MEMORY_ENABLED=true"}

    collections = [c.strip() for c in collection.split(",")] if collection != "all" else ["decisions", "reviews", "research", "default"]

    all_results = []
    for col in collections:
        try:
            results = store.search(query, col, top_k=top_k // len(collections) or 1, min_score=min_score)
            for r in results:
                r.setdefault("collection", col)
                all_results.append(r)
        except Exception:
            continue

    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    all_results = all_results[:top_k]

    return {
        "success": True,
        "data": {
            "query": query,
            "results": all_results,
            "total_found": len(all_results),
            "backend": getattr(store, "__class__", type(store)).__name__,
        },
    }


def register(registry):
    registry.register(Tool(
        name="memory_search",
        description="语义检索历史记忆：搜索相似的历史决策/复盘报告/研报摘要",
        input_schema=MemorySearchInput,
        handler=memory_search,
        agent_name="admin",
        tier="core",
    ))
