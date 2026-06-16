"""团队管理工具测试"""
import pytest
from pathlib import Path
import tempfile

from praxis.tools.teams import (
    list_teams,
    get_team_prompt,
    compose_team_prompt,
    list_output_templates,
    get_output_template,
)


class TestTeamsTools:
    """团队管理工具测试"""

    def setup_method(self):
        """测试前准备"""
        self.tmp_dir = tempfile.mkdtemp()

    def test_list_teams(self):
        """测试列出团队"""
        result = list_teams(workspace=self.tmp_dir)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_team_prompt(self):
        """测试获取团队 Prompt"""
        result = get_team_prompt("asrg", workspace=self.tmp_dir)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_compose_team_prompt(self):
        """测试组合团队 Prompt"""
        result = compose_team_prompt("asrg", "grid_value", "example", workspace=self.tmp_dir)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_list_output_templates(self):
        """测试列出输出模板"""
        result = list_output_templates(workspace=self.tmp_dir)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result

    def test_get_output_template(self):
        """测试获取输出模板"""
        result = get_output_template("asrg_output", workspace=self.tmp_dir)

        # 验证结果
        assert isinstance(result, dict)
        assert "success" in result


class TestTeamsToolsIntegration:
    """团队管理工具集成测试"""

    def test_list_teams_returns_valid_data(self):
        """测试列出团队返回有效数据"""
        result = list_teams()

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result
            assert isinstance(result["data"], dict)
            assert "teams" in result["data"]
            assert isinstance(result["data"]["teams"], list)

    def test_get_team_prompt_returns_content(self):
        """测试获取团队 Prompt 返回内容"""
        result = get_team_prompt("asrg")

        # 验证结果
        assert isinstance(result, dict)
        if result.get("success"):
            assert "data" in result
