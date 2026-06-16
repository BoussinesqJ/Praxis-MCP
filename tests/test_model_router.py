"""
Praxis v3.0 模型分级路由测试

测试重点：
- model_hint 映射正确性
- 默认行为（未知 agent 返回 deep）
- 路由摘要格式
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from praxis_sdk.core.model_router import (
    get_model_hint,
    get_model_for_agent,
    get_routing_summary,
    ModelHint,
    AGENT_MODEL_MAP,
)


class TestModelRouter:
    """模型路由测试套件。"""

    def test_quick_agents(self):
        """测试 quick 类型 agent 映射。"""
        quick_agents = [
            "asrg_ethan", "asrg_james", "asrg_kevin",
            "trading_analysts", "trading_trader",
        ]
        for agent in quick_agents:
            assert get_model_hint(agent) == ModelHint.QUICK, \
                f"{agent} should be quick, got {get_model_hint(agent)}"

    def test_deep_agents(self):
        """测试 deep 类型 agent 映射。"""
        deep_agents = [
            "asrg_frank", "asrg_gavin",
            "masters_buffett", "masters_growth", "masters_risk", "masters_arthur",
            "trading_debate", "trading_risk", "trading_dominic",
            "lcd_arbitration",
        ]
        for agent in deep_agents:
            assert get_model_hint(agent) == ModelHint.DEEP, \
                f"{agent} should be deep, got {get_model_hint(agent)}"

    def test_unknown_agent_defaults_to_deep(self):
        """测试未知 agent 默认返回 deep（安全侧）。"""
        assert get_model_hint("unknown_agent") == ModelHint.DEEP

    def test_agent_map_ratio(self):
        """测试 quick:deep 比例约为 7:6。"""
        quick_count = sum(1 for v in AGENT_MODEL_MAP.values() if v == ModelHint.QUICK)
        deep_count = sum(1 for v in AGENT_MODEL_MAP.values() if v == ModelHint.DEEP)
        # 应该有 5 quick 和 10 deep（或接近）
        assert quick_count >= 4, f"Expected at least 4 quick agents, got {quick_count}"
        assert deep_count >= 6, f"Expected at least 6 deep agents, got {deep_count}"
        print(f"  Ratio: {quick_count} quick : {deep_count} deep")

    def test_total_agents_count(self):
        """测试总 agent 数量。"""
        assert len(AGENT_MODEL_MAP) == 15

    def test_env_var_override(self):
        """测试环境变量覆盖模型。"""
        # 设置环境变量
        os.environ["PRAXIS_DEEP_MODEL"] = "gpt-5.5"
        os.environ["PRAXIS_QUICK_MODEL"] = "gpt-5.4-mini"

        try:
            assert get_model_for_agent("asrg_ethan") == "gpt-5.4-mini"
            assert get_model_for_agent("trading_dominic") == "gpt-5.5"
        finally:
            # 清理环境变量
            del os.environ["PRAXIS_DEEP_MODEL"]
            del os.environ["PRAXIS_QUICK_MODEL"]

    def test_routing_summary(self):
        """测试路由摘要格式。"""
        summary = get_routing_summary()
        assert "deep_model" in summary
        assert "quick_model" in summary
        assert "deep_agents" in summary
        assert "quick_agents" in summary
        assert "ratio" in summary
        assert isinstance(summary["deep_agents"], list)
        assert isinstance(summary["quick_agents"], list)


def run_tests():
    """运行所有测试。"""
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
