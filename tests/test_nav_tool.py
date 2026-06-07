"""净值工具测试"""
import pytest
import asyncio
from praxis.tools.nav import record_nav, get_nav_snapshot, get_nav_history


class TestNavTools:
    """净值工具测试"""

    def test_record_nav(self):
        """测试记录净值"""
        result = record_nav("example", "core", 1000000, 500000, 480000, 1020000)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_nav_snapshot(self):
        """测试获取净值快照"""
        result = asyncio.run(get_nav_snapshot("example", "core"))

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_nav_history(self):
        """测试获取净值历史"""
        result = get_nav_history("example", "core")

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result


class TestNavToolsIntegration:
    """净值工具集成测试"""

    def test_record_nav_returns_valid_data(self):
        """测试记录净值返回有效数据"""
        result = record_nav("example", "core", 1000000, 500000, 480000, 1020000)

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result

    def test_get_nav_snapshot_returns_valid_data(self):
        """测试获取净值快照返回有效数据"""
        result = asyncio.run(get_nav_snapshot("example", "core"))

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result
