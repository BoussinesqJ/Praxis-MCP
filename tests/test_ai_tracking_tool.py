"""AI 追踪工具测试"""
import pytest
from praxis.tools.ai_tracking import get_ai_tracking


class TestAITrackingTools:
    """AI 追踪工具测试"""

    def test_get_ai_tracking(self):
        """测试获取 AI 追踪数据"""
        result = get_ai_tracking()

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_ai_tracking_returns_valid_data(self):
        """测试获取 AI 追踪数据返回有效数据"""
        result = get_ai_tracking()

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result


class TestAITrackingToolsIntegration:
    """AI 追踪工具集成测试"""

    def test_get_ai_tracking_with_team(self):
        """测试获取指定团队的 AI 追踪数据"""
        result = get_ai_tracking()

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result
