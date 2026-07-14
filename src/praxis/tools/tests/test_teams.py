"""团队管理工具测试 — teams 函数."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from praxis.tools.teams import teams, BUILTIN_TEAMS, _ensure_team_dir, _get_config_dir


@pytest.mark.asyncio
class TestList:
    """list 测试."""

    async def test_list_returns_three_teams(self):
        """list 返回 3 个团队."""
        result = await teams(action="list")
        assert result["success"] is True
        assert result["data"]["count"] == 3
        team_names = [t["name"] for t in result["data"]["teams"]]
        assert "asrg" in team_names
        assert "masters" in team_names
        assert "trading" in team_names


@pytest.mark.asyncio
class TestInfo:
    """info 测试."""

    async def test_info_asrg(self):
        """info 返回 ASRG 团队详情."""
        result = await teams(action="info", team_name="asrg")
        assert result["success"] is True
        team = result["data"]["team"]
        assert team["name"] == "ASRG"
        assert team["role"] == "宏观策略"
        assert "default_prompt" in team

    async def test_info_trading(self):
        """info 返回 Trading 团队详情."""
        result = await teams(action="info", team_name="trading")
        assert result["success"] is True
        assert result["data"]["team"]["model_hint"] == "quick"


@pytest.mark.asyncio
class TestPrompts:
    """prompts 测试."""

    async def test_prompts_returns_templates(self, monkeypatch, tmp_path):
        """prompts 返回模板列表."""
        # 创建临时 config/teams/asrg/ 目录和文件
        config_dir = tmp_path / "config" / "teams" / "asrg"
        config_dir.mkdir(parents=True)
        (config_dir / "system_prompt.md").write_text("# System Prompt\nTest", encoding="utf-8")
        (config_dir / "user_prompt.txt").write_text("User prompt test", encoding="utf-8")

        # 替换 _get_config_dir 返回临时路径
        import praxis.tools.teams as team_module
        monkeypatch.setattr(team_module, "_get_config_dir", lambda: tmp_path / "config" / "teams")
        monkeypatch.setattr(team_module, "_ensure_team_dir", lambda name: tmp_path / "config" / "teams" / name)

        result = await teams(action="prompts", team_name="asrg")
        assert result["success"] is True
        assert "templates" in result["data"]
        assert len(result["data"]["templates"]) >= 1

    async def test_prompts_default_when_no_files(self, monkeypatch, tmp_path):
        """无文件时返回默认 prompt."""
        import praxis.tools.teams as team_module
        monkeypatch.setattr(team_module, "_get_config_dir", lambda: tmp_path / "config" / "teams")
        monkeypatch.setattr(team_module, "_list_prompts", lambda name: [])

        result = await teams(action="prompts", team_name="asrg")
        assert result["success"] is True
        assert "default_content" in result["data"]


@pytest.mark.asyncio
class TestUpdatePrompt:
    """update_prompt 测试."""

    async def test_update_prompt(self, monkeypatch, tmp_path):
        """update_prompt 更新 prompt 内容."""
        config_dir = tmp_path / "config" / "teams" / "asrg"
        config_dir.mkdir(parents=True)

        import praxis.tools.teams as team_module
        monkeypatch.setattr(team_module, "_get_config_dir", lambda: tmp_path / "config" / "teams")
        monkeypatch.setattr(team_module, "_ensure_team_dir", lambda name: config_dir)

        new_content = "# Updated Prompt\nBuy more, sell less."
        result = await teams(
            action="update_prompt",
            team_name="asrg",
            prompt_file="updated.md",
            _deps={"prompt_content": new_content},
        )

        assert result["success"] is True
        assert result["data"]["team"] == "asrg"
        assert result["data"]["file"] == "updated.md"

        # 验证文件内容
        saved = (config_dir / "updated.md").read_text(encoding="utf-8")
        assert saved == new_content


@pytest.mark.asyncio
class TestNonexistentTeam:
    """不存在团队测试."""

    async def test_nonexistent_team_info(self):
        """不存在的团队 info 返回 error."""
        result = await teams(action="info", team_name="ghost")
        assert result["success"] is False
        assert "未知" in result.get("error", "")

    async def test_nonexistent_team_prompts(self):
        """不存在的团队 prompts 返回 error."""
        result = await teams(action="prompts", team_name="ghost")
        assert result["success"] is False


@pytest.mark.asyncio
class TestInvalidAction:
    """无效 action 测试."""

    async def test_invalid_action(self):
        """无效 action 返回 error."""
        result = await teams(action="foobar")
        assert result["success"] is False
        assert "未知" in result.get("error", "")
