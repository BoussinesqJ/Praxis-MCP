"""进化记忆存储

将每次进化审计归档为结构化知识，支持回溯查询和时间线生成。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class EvolutionMemory(BaseModel):
    """进化记忆记录"""
    memory_id: str
    timestamp: str
    trigger_event: str          # transaction / nav_record / sentinel / manual
    strategy_name: str
    evaluation_summary: str
    dimensions: list[dict] = []
    suggestions: list[dict] = []
    decision: str = "pending"   # approved / rejected / pending
    rejection_reason: str | None = None
    outcome: str | None = None
    outcome_metrics: dict | None = None


class EvolutionMemoryStore:
    """进化记忆存储"""

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._memory_dir = self._workspace / "data" / "evolution_memory"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        trigger_event: str,
        strategy_name: str,
        evaluation_summary: str,
        dimensions: list[dict] | None = None,
        suggestions: list[dict] | None = None,
    ) -> str:
        """记录进化记忆"""
        timestamp = datetime.now()
        # 使用微秒 + 计数器避免 ID 冲突
        existing = list(self._memory_dir.glob("evo-*.json"))
        counter = len(existing) + 1
        memory_id = f"evo-{timestamp.strftime('%Y%m%d-%H%M%S')}-{counter:03d}"

        memory = EvolutionMemory(
            memory_id=memory_id,
            timestamp=timestamp.isoformat(),
            trigger_event=trigger_event,
            strategy_name=strategy_name,
            evaluation_summary=evaluation_summary,
            dimensions=dimensions or [],
            suggestions=suggestions or [],
        )

        path = self._memory_dir / f"{memory_id}.json"
        path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def load_all(self) -> list[EvolutionMemory]:
        """加载所有进化记忆"""
        memories = []
        for f in sorted(self._memory_dir.glob("evo-*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                memories.append(EvolutionMemory(**data))
            except Exception:
                continue
        return memories

    def query_similar(self, situation: str, limit: int = 5) -> list[EvolutionMemory]:
        """查询类似情况的历史进化记录

        简单实现：按维度名称关键词匹配。
        后续可升级为向量相似度搜索。
        """
        memories = self.load_all()
        scored: list[tuple[int, EvolutionMemory]] = []
        for m in memories:
            score = 0
            # 匹配维度名称（维度名是 situation 的子串）
            for d in m.dimensions:
                dim_name = d.get("name", "")
                if dim_name and dim_name in situation:
                    score += 2
            # 匹配策略名称
            if m.strategy_name in situation:
                score += 1
            # 匹配评估摘要中的关键词
            for word in situation.split():
                if word in m.evaluation_summary:
                    score += 1
            if score > 0:
                scored.append((score, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    def update_decision(
        self,
        memory_id: str,
        decision: str,
        rejection_reason: str | None = None,
    ) -> bool:
        """更新进化记忆的决策状态"""
        path = self._memory_dir / f"{memory_id}.json"
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["decision"] = decision
            if rejection_reason:
                data["rejection_reason"] = rejection_reason
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def update_outcome(
        self,
        memory_id: str,
        outcome: str,
        outcome_metrics: dict | None = None,
    ) -> bool:
        """回填进化记忆的实际效果（延迟回填）"""
        path = self._memory_dir / f"{memory_id}.json"
        if not path.exists():
            return False

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["outcome"] = outcome
            if outcome_metrics:
                data["outcome_metrics"] = outcome_metrics
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception:
            return False

    def generate_timeline(self, strategy_name: str) -> str:
        """生成进化时间线 Markdown"""
        memories = sorted(
            [m for m in self.load_all() if m.strategy_name == strategy_name],
            key=lambda m: m.timestamp,
        )

        lines = [
            f"# 策略进化时间线: {strategy_name}",
            "",
            f"> 自动生成 | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "| 日期 | 触发事件 | 维度 | 决策 | 效果 |",
            "|:---|:---|:---|:---:|:---|",
        ]

        if not memories:
            lines.append("| — | — | 暂无进化记录 | — | — |")
        else:
            for m in memories:
                dims = ", ".join(
                    d.get("name", "?") for d in m.dimensions
                ) or "—"
                outcome = m.outcome or "—"
                lines.append(
                    f"| {m.timestamp[:10]} | {m.trigger_event} | {dims} | {m.decision} | {outcome} |"
                )

        # 统计摘要
        total = len(memories)
        approved = sum(1 for m in memories if m.decision == "approved")
        rejected = sum(1 for m in memories if m.decision == "rejected")
        pending = sum(1 for m in memories if m.decision == "pending")

        lines.extend([
            "",
            "## 统计",
            f"- 总记录: {total}",
            f"- 已审批: {approved}",
            f"- 已拒绝: {rejected}",
            f"- 待审批: {pending}",
        ])

        timeline_path = self._workspace / "deliverables" / "evolution" / f"timeline_{strategy_name}.md"
        timeline_path.parent.mkdir(parents=True, exist_ok=True)
        timeline_path.write_text("\n".join(lines), encoding="utf-8")

        return "\n".join(lines)
