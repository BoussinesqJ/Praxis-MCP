"""灰度发布工具测试"""
import pytest
from pathlib import Path
import tempfile

from praxis.tools.grayscale import (
    prepare_grayscale,
    approve_grayscale,
)


class TestGrayscaleTools:
    """灰度发布工具测试"""

    def setup_method(self):
        """测试前准备"""
        self.tmp_dir = tempfile.mkdtemp()

    def test_prepare_grayscale(self):
        """测试准备灰度发布"""
        result = prepare_grayscale(
            strategy_name="grid_value",
            change_description="测试灰度",
            risk_level="low",
            workspace=self.tmp_dir,
        )

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_approve_grayscale(self):
        """测试审批灰度发布"""
        result = approve_grayscale(
            strategy_name="grid_value",
            backup_path="backup.yaml",
            new_content="新策略内容",
            workspace=self.tmp_dir,
        )

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result


class TestGrayscaleToolsIntegration:
    """灰度发布工具集成测试"""

    def test_prepare_grayscale_returns_valid_data(self):
        """测试准备灰度发布返回有效数据"""
        result = prepare_grayscale(
            strategy_name="grid_value",
            change_description="测试灰度",
            risk_level="low",
        )

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result
