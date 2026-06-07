"""灰度发布测试"""
import pytest
from pathlib import Path
import tempfile

from praxis.engine.grayscale import (
    StrategyGrayscale,
    GrayscaleConfig,
    GrayscaleResult,
)


class TestStrategyGrayscale:
    """策略灰度发布测试"""

    def setup_method(self):
        """测试前准备"""
        self.tmp_dir = tempfile.mkdtemp()
        self.grayscale = StrategyGrayscale(self.tmp_dir)

    def test_prepare_grayscale(self):
        """测试准备灰度发布"""
        # 准备灰度配置
        config = GrayscaleConfig(
            strategy_name="grid_value",
            change_description="测试灰度",
            risk_level="low",
        )
        result = self.grayscale.prepare_grayscale(config)

        # 验证结果
        assert isinstance(result, GrayscaleResult)
        assert result.strategy_name == "grid_value"

    def test_grayscale_config(self):
        """测试灰度配置"""
        config = GrayscaleConfig(
            strategy_name="grid_value",
            change_description="测试灰度",
            risk_level="low",
        )

        # 验证配置
        assert config.strategy_name == "grid_value"
        assert config.change_description == "测试灰度"
        assert config.risk_level == "low"

    def test_grayscale_result(self):
        """测试灰度结果"""
        result = GrayscaleResult(
            strategy_name="grid_value",
            change_description="测试灰度",
            risk_level="low",
            backup_path="backup.yaml",
            validation_passed=True,
            message="灰度验证通过",
        )

        # 验证结果
        assert result.strategy_name == "grid_value"
        assert result.validation_passed is True
        assert result.message == "灰度验证通过"
