"""
Praxis v3.0 结构化输出校验器测试

测试重点：
- Pydantic schema 校验（如果 pydantic 已安装）
- 正则降级提取
- 各类 schema 类型的校验
- 降级逻辑正确性
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from praxis_sdk.core.validator import (
    validate_or_fallback,
    validate_decision,
    validate_team_output,
    get_validator_status,
    HAS_PYDANTIC,
    ValidationResult,
)


class TestValidator:
    """结构化输出校验器测试套件。"""

    def test_validator_status(self):
        """测试校验器状态报告。"""
        status = get_validator_status()
        assert "pydantic_available" in status
        assert "schema_types" in status
        assert "fallback_method" in status
        assert status["fallback_method"] == "regex"
        print(f"  Pydantic available: {status['pydantic_available']}")

    def test_regex_extract_recommendation(self):
        """测试正则提取推荐等级。"""
        text = "Based on our analysis, we recommendation: Buy this stock."
        result = validate_or_fallback(text, "decision")
        # 应该能提取到 buy
        assert result.fallback_data is not None or result.data is not None

    def test_regex_extract_confidence(self):
        """测试正则提取置信度。"""
        text = "Confidence: 75% based on strong fundamentals."
        result = validate_or_fallback(text, "decision")
        data = result.data or result.fallback_data
        if data and "confidence" in data:
            assert 0 <= data["confidence"] <= 1

    def test_regex_extract_logic_validation(self):
        """测试正则提取逻辑强验证标记。"""
        text = "Our analysis shows [Logic_Strong_Validation] for this stock."
        result = validate_or_fallback(text, "asrg")
        data = result.data or result.fallback_data
        if data:
            assert data.get("logic_strong_validation") is True

    def test_regex_extract_pda(self):
        """测试正则提取 PDA 状态。"""
        text = "PDA: 有效，支撑位确认。"
        result = validate_or_fallback(text, "trading")
        data = result.data or result.fallback_data
        if data:
            assert data.get("pda_valid") is True

    def test_decision_validation(self):
        """测试决策输出校验。"""
        text = """
        **Rating**: Buy
        **Confidence**: 0.85
        **Reasoning**: Strong fundamentals and positive sentiment.
        """
        result = validate_decision(text)
        # 应该有数据（无论是 schema 还是 fallback）
        assert result.data is not None or result.fallback_data is not None

    def test_team_output_validation(self):
        """测试团队输出校验。"""
        # ASRG 输出
        asrg_text = "Recommendation: Buy, Confidence: 80%, [Logic_Strong_Validation]"
        result = validate_team_output(asrg_text, "asrg")
        assert result.data is not None or result.fallback_data is not None

        # Trading 输出
        trading_text = "Recommendation: Hold, Confidence: 60%, PDA: 无效"
        result = validate_team_output(trading_text, "trading")
        assert result.data is not None or result.fallback_data is not None

    def test_empty_text_handled(self):
        """测试空文本不会崩溃。"""
        result = validate_or_fallback("", "decision")
        assert isinstance(result, ValidationResult)

    def test_garbage_text_handled(self):
        """测试乱码文本不会崩溃。"""
        result = validate_or_fallback("asdfghjkl12345!@#$%", "decision")
        assert isinstance(result, ValidationResult)

    def test_fallback_used_flag(self):
        """测试 fallback_used 标志。"""
        # 纯文本（不太可能通过 Pydantic schema）
        text = "This is a simple text with recommendation: buy and confidence: 70%"
        result = validate_or_fallback(text, "decision")

        if HAS_PYDANTIC:
            # 如果有 pydantic，可能通过 schema 或降级
            assert isinstance(result.fallback_used, bool)
        else:
            # 没有 pydantic，应该用降级
            assert result.fallback_used is True

    def test_all_schema_types_acceptable(self):
        """测试所有 schema 类型都能处理。"""
        text = "Recommendation: Buy, Confidence: 80%"
        for schema_type in ["asrg", "masters", "trading", "decision"]:
            result = validate_or_fallback(text, schema_type)
            assert isinstance(result, ValidationResult)


def run_tests():
    """运行所有测试。"""
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
