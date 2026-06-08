"""Tests for multi-agent consensus engine"""
import json
import pytest
from pathlib import Path

from praxis.engine.consensus import AgentDecision, AgentDecisionStore, ConsensusEngine


@pytest.fixture
def store(tmp_path):
    return AgentDecisionStore(str(tmp_path))


@pytest.fixture
def engine(store):
    return ConsensusEngine(store)


def _make_decision(agent_id: str, ticker: str, action: str, confidence: float = 0.7, timestamp: str = "2026-06-08T10:00:00") -> AgentDecision:
    return AgentDecision(
        decision_id=f"test-{agent_id}-{action}",
        agent_id=agent_id,
        timestamp=timestamp,
        ticker=ticker,
        action=action,
        confidence=confidence,
        reasoning=f"{agent_id} 认为应 {action}",
    )


class TestRecordDecision:
    """决策记录测试"""

    def test_record_creates_file(self, store):
        """记录应创建 JSONL 文件"""
        d = _make_decision("reasonix", "STOCK_A", "buy")
        store.record(d)
        path = store._decisions_dir / "reasonix.jsonl"
        assert path.exists()

    def test_load_agent_decisions(self, store):
        """加载某 Agent 的决策"""
        store.record(_make_decision("reasonix", "STOCK_A", "buy"))
        store.record(_make_decision("reasonix", "ETF_300", "hold"))
        decisions = store.load_agent_decisions("reasonix")
        assert len(decisions) == 2

    def test_load_ticker_decisions(self, store):
        """加载某标的的多 Agent 决策"""
        store.record(_make_decision("reasonix", "STOCK_A", "buy"))
        store.record(_make_decision("gemini", "STOCK_A", "buy"))
        store.record(_make_decision("reasonix", "ETF_300", "hold"))
        decisions = store.load_ticker_decisions("STOCK_A")
        assert len(decisions) == 2


class TestConsensus:
    """共识检查测试"""

    def test_consensus_achieved(self, store, engine):
        """2/3 agents agree → 共识"""
        store.record(_make_decision("reasonix", "STOCK_A", "buy"))
        store.record(_make_decision("gemini", "STOCK_A", "buy"))
        store.record(_make_decision("claude", "STOCK_A", "sell"))

        result = engine.check_consensus("STOCK_A")
        assert result["consensus"] is True
        assert result["recommended_action"] == "buy"
        assert result["total_agents"] == 3
        assert result["consensus_ratio"] > 0.5

    def test_consensus_not_achieved(self, store, engine):
        """无多数 → 未达共识"""
        store.record(_make_decision("reasonix", "STOCK_A", "buy"))
        store.record(_make_decision("gemini", "STOCK_A", "sell"))
        store.record(_make_decision("claude", "STOCK_A", "hold"))

        result = engine.check_consensus("STOCK_A")
        assert result["consensus"] is False
        assert result["recommended_action"] is None

    def test_two_agents_consensus(self, store, engine):
        """2/2 agents agree"""
        store.record(_make_decision("reasonix", "ETF_300", "hold"))
        store.record(_make_decision("gemini", "ETF_300", "hold"))

        result = engine.check_consensus("ETF_300")
        assert result["consensus"] is True
        assert result["recommended_action"] == "hold"

    def test_no_decisions(self, engine):
        """无决策记录"""
        result = engine.check_consensus("000000")
        assert result["consensus"] is False
        assert result["total_agents"] == 0

    def test_same_agent_latest_only(self, store, engine):
        """同一 Agent 只取最新决策"""
        store.record(_make_decision("reasonix", "STOCK_A", "buy", timestamp="2026-06-08T10:00:00"))
        store.record(_make_decision("reasonix", "STOCK_A", "sell", timestamp="2026-06-08T11:00:00"))
        store.record(_make_decision("gemini", "STOCK_A", "sell", timestamp="2026-06-08T10:00:00"))

        result = engine.check_consensus("STOCK_A")
        assert result["consensus"] is True
        assert result["recommended_action"] == "sell"
        assert result["total_agents"] == 2  # 只有 2 个不同 Agent


class TestRankAgents:
    """Agent 排名测试"""

    def test_ranking(self, store, engine):
        """排名按决策数量排序"""
        for _ in range(5):
            store.record(_make_decision("reasonix", "STOCK_A", "buy"))
        for _ in range(3):
            store.record(_make_decision("gemini", "STOCK_A", "hold"))

        rankings = engine.rank_agents()
        assert len(rankings) == 2
        assert rankings[0]["agent_id"] == "reasonix"
        assert rankings[0]["total_decisions"] == 5
        assert rankings[1]["agent_id"] == "gemini"

    def test_empty_rankings(self, engine):
        """无 Agent 时返回空"""
        rankings = engine.rank_agents()
        assert rankings == []
