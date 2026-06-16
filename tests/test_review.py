"""复盘工具测试"""
import pytest
import asyncio
from pathlib import Path
import tempfile

from praxis.tools.review import (
    fill_reviews,
    get_review_summary,
    get_confidence_calibration,
)


class TestReviewTools:
    """复盘工具测试"""

    def setup_method(self):
        """测试前准备"""
        self.tmp_dir = tempfile.mkdtemp()

    def test_fill_reviews(self):
        """测试回填复盘"""
        result = asyncio.run(fill_reviews(workspace=self.tmp_dir))

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_review_summary(self):
        """测试获取复盘汇总"""
        result = get_review_summary(workspace=self.tmp_dir)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_confidence_calibration(self):
        """测试获取置信度校准"""
        result = get_confidence_calibration("asrg", workspace=self.tmp_dir)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result


class TestReviewToolsIntegration:
    """复盘工具集成测试"""

    def test_fill_reviews_returns_valid_data(self):
        """测试回填复盘返回有效数据"""
        result = asyncio.run(fill_reviews())

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result

    def test_get_review_summary_returns_valid_data(self):
        """测试获取复盘汇总返回有效数据"""
        result = get_review_summary()

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result
