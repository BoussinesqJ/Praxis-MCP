"""
Praxis v3.0 配置模块测试

测试重点：
- 数据供应商配置
- 降级链逻辑
- 环境变量覆盖
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from praxis_sdk.config import (
    get_data_vendor,
    get_vendor_fallback_chain,
    get_config_summary,
    VALID_VENDORS,
    CHECKPOINT_ENABLED,
)


class TestConfig:
    """配置模块测试套件。"""

    def test_default_vendor(self):
        """测试默认数据供应商。"""
        vendor = get_data_vendor()
        assert vendor in VALID_VENDORS
        assert vendor == "akshare"

    def test_env_var_override(self):
        """测试环境变量覆盖。"""
        os.environ["PRAXIS_DATA_VENDOR"] = "eastmoney"
        try:
            vendor = get_data_vendor()
            assert vendor == "eastmoney"
        finally:
            del os.environ["PRAXIS_DATA_VENDOR"]

    def test_invalid_vendor_fallback(self):
        """测试非法供应商回退到 akshare。"""
        os.environ["PRAXIS_DATA_VENDOR"] = "invalid_vendor"
        try:
            vendor = get_data_vendor()
            assert vendor == "akshare"
        finally:
            del os.environ["PRAXIS_DATA_VENDOR"]

    def test_fallback_chain_starts_with_current(self):
        """测试降级链以当前供应商开头。"""
        chain = get_vendor_fallback_chain()
        assert chain[0] == get_data_vendor()
        assert len(chain) == 3

    def test_fallback_chain_contains_all(self):
        """测试降级链包含所有供应商。"""
        chain = get_vendor_fallback_chain()
        for vendor in VALID_VENDORS:
            assert vendor in chain

    def test_config_summary(self):
        """测试配置摘要。"""
        summary = get_config_summary()
        assert "data_vendor" in summary
        assert "vendor_fallback_chain" in summary
        assert "checkpoint_enabled" in summary
        assert "deep_model" in summary
        assert "quick_model" in summary

    def test_checkpoint_enabled_default(self):
        """测试断点默认启用。"""
        assert CHECKPOINT_ENABLED is True


def run_tests():
    """运行所有测试。"""
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
