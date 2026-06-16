"""版本对比工具测试"""
import pytest
import asyncio
from praxis.tools.version_compare import compare_versions


class TestVersionCompareTools:
    """版本对比工具测试"""

    def test_compare_versions(self):
        """测试版本对比"""
        result = asyncio.run(compare_versions("v1.0", "v1.1"))

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_compare_versions_returns_valid_data(self):
        """测试版本对比返回有效数据"""
        result = asyncio.run(compare_versions("v1.0", "v1.1"))

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result


class TestVersionCompareToolsIntegration:
    """版本对比工具集成测试"""

    def test_compare_versions_with_different_names(self):
        """测试不同版本名称的对比"""
        # 测试不同的版本名称
        for v1, v2 in [("v1.0", "v1.1"), ("v2.0", "v2.1"), ("v3.0", "v3.1")]:
            result = asyncio.run(compare_versions(v1, v2))
            assert isinstance(result, dict)
            assert "success" in result
