"""多 Agent 共识引擎单元测试 — ConsensusEngine + AgentDecisionStore."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from praxis.engine.consensus import ConsensusEngine, AgentDecisionStore, AgentDecision


class TestAgentDecision:
    """AgentDecision 模型."""

    def test_agent_decision_create(self):
        """构造 AgentDecision."""
        d = AgentDecision(
            agent_id="reasonix",
            ticker="600519",
            action="buy",
            confidence=0.85,
            reasoning="看好茅台长期价值",
            price_target=2000.0,
            stop_loss=1700.0,
        )
        assert d.agent_id == "reasonix"
        assert d.ticker == "600519"
        assert d.confidence == 0.85
        assert d.decision_id == ""  # 未设置


class TestRecordAndLoad:
    """记录与加载."""

    def test_record_and_load(self, tmp_path):
        """记录决策后可加载."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        d = AgentDecision(
            agent_id="reasonix", ticker="600519", action="buy", confidence=0.9,
        )
        did = store.record(d)
        assert did.startswith("agent-dec-")

        loaded = store.load_agent_decisions("reasonix", limit=10)
        assert len(loaded) == 1
        assert loaded[0].ticker == "600519"
        assert loaded[0].confidence == 0.9

    def test_record_auto_generates_id(self, tmp_path):
        """未提供 decision_id 自动生成."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        d = AgentDecision(
            agent_id="claude", ticker="159915", action="hold", confidence=0.3,
        )
        did = store.record(d)
        assert d.decision_id == did
        assert did.startswith("agent-dec-")


class TestConsensusReached:
    """共识达成."""

    def test_consensus_reached(self, tmp_path):
        """2+ Agent 达成共识."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        store.record(AgentDecision(agent_id="reasonix", ticker="600519", action="buy", confidence=0.9))
        store.record(AgentDecision(agent_id="gemini", ticker="600519", action="buy", confidence=0.8))
        store.record(AgentDecision(agent_id="claude", ticker="600519", action="buy", confidence=0.7))

        engine = ConsensusEngine(store)
        result = engine.check_consensus("600519", min_agents=2)
        assert result["consensus_reached"] is True

    def test_consensus_not_reached(self, tmp_path):
        """动作不一致时未达成共识."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        store.record(AgentDecision(agent_id="reasonix", ticker="600519", action="buy", confidence=0.9))
        store.record(AgentDecision(agent_id="gemini", ticker="600519", action="sell", confidence=0.8))

        engine = ConsensusEngine(store)
        result = engine.check_consensus("600519", min_agents=2)
        assert result["consensus_reached"] is False


class TestInsufficientAgents:
    """Agent 不足."""

    def test_insufficient_agents(self, tmp_path):
        """参与 Agent 不足时无法形成共识."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        store.record(AgentDecision(agent_id="reasonix", ticker="600519", action="buy", confidence=0.9))

        engine = ConsensusEngine(store)
        result = engine.check_consensus("600519", min_agents=2)
        assert result["consensus_reached"] is False
        assert "不足" in result["reason"]


class TestRankAgents:
    """排名."""

    def test_rank_agents(self, tmp_path):
        """按决策数×平均置信度排名."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        # reasonix: 3 decisions
        for _ in range(3):
            store.record(AgentDecision(agent_id="reasonix", ticker="600519", action="buy", confidence=0.9))
        # gemini: 1 decision
        store.record(AgentDecision(agent_id="gemini", ticker="159915", action="sell", confidence=0.5))

        engine = ConsensusEngine(store)
        rankings = engine.rank_agents()
        assert len(rankings) == 3  # reasonix, gemini, claude
        assert rankings[0]["agent_id"] == "reasonix"  # 决策最多
        assert rankings[0]["total_decisions"] == 3


class TestLoadLimit:
    """limit 参数."""

    def test_load_limit(self, tmp_path):
        """limit 限制返回数量."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        for i in range(15):
            store.record(AgentDecision(
                agent_id="reasonix", ticker=f"00000{i%10}",
                action="buy", confidence=0.5,
            ))

        loaded = store.load_agent_decisions("reasonix", limit=5)
        assert len(loaded) == 5


class TestEmptyStore:
    """空存储."""

    def test_empty_store_load(self, tmp_path):
        """空存储加载返回空列表."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        loaded = store.load_agent_decisions("nonexistent", limit=10)
        assert loaded == []

    def test_empty_store_consensus(self, tmp_path):
        """空存储共识检查."""
        store = AgentDecisionStore(workspace=str(tmp_path))
        engine = ConsensusEngine(store)
        result = engine.check_consensus("600519")
        assert result["consensus_reached"] is False
