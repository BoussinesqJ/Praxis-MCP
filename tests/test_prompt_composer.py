"""Prompt 组合器测试"""
import pytest
from pathlib import Path
import tempfile

from praxis.engine.prompt_composer import PromptComposer


class TestPromptComposer:
    """Prompt 组合器测试"""

    def setup_method(self):
        """测试前准备"""
        self.tmp_dir = tempfile.mkdtemp()
        self.composer = PromptComposer(self.tmp_dir)

    def test_compose_base_prompt(self):
        """测试基础 Prompt 组合"""
        # 准备测试数据
        team_name = "asrg"
        strategy_name = "grid_value"
        investor_id = "example"

        # 组合 Prompt
        result = self.composer.compose(team_name, strategy_name, investor_id)

        # 验证结果
        assert isinstance(result, str)
        # 结果可能为空（如果文件不存在）

    def test_compose_strategy_prompt(self):
        """测试策略 Prompt 组合"""
        # 准备测试数据
        team_name = "trading"
        strategy_name = "grid_value"
        investor_id = "example"

        # 组合 Prompt
        result = self.composer.compose(team_name, strategy_name, investor_id)

        # 验证结果
        assert isinstance(result, str)

    def test_compose_investor_prompt(self):
        """测试投资者 Prompt 组合"""
        # 准备测试数据
        team_name = "masters"
        strategy_name = "grid_value"
        investor_id = "example"

        # 组合 Prompt
        result = self.composer.compose(team_name, strategy_name, investor_id)

        # 验证结果
        assert isinstance(result, str)

    def test_compose_with_different_teams(self):
        """测试不同团队的 Prompt 组合"""
        # 准备测试数据
        strategy_name = "grid_value"
        investor_id = "example"

        # 测试不同团队
        for team_name in ["asrg", "trading", "masters"]:
            result = self.composer.compose(team_name, strategy_name, investor_id)
            assert isinstance(result, str)

    def test_compose_returns_string(self):
        """测试返回字符串类型"""
        # 准备测试数据
        team_name = "asrg"
        strategy_name = "grid_value"
        investor_id = "example"

        # 组合 Prompt
        result = self.composer.compose(team_name, strategy_name, investor_id)

        # 验证返回类型
        assert isinstance(result, str)
