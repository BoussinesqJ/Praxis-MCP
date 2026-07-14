"""工作区工具测试 — discover_workspace 函数."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from praxis.tools.workspace import discover_workspace


def _make_deps(workspace_path=None):
    """构造 _deps 字典."""
    return {"workspace": workspace_path or "."}


class TestDiscover:
    """discover 测试."""

    @pytest.mark.asyncio
    async def test_discover_normal(self):
        """正常发现 — 返回工作区结构."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            investors_dir = root / "config" / "investors"
            portfolios_dir = root / "config" / "portfolios"
            data_dir = root / "data"
            investors_dir.mkdir(parents=True)
            portfolios_dir.mkdir(parents=True)
            data_dir.mkdir(parents=True)

            result = await discover_workspace(
                action="discover",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            assert "investors" in result["data"]
            assert "portfolios" in result["data"]

    @pytest.mark.asyncio
    async def test_empty_workspace(self):
        """空工作区 — 所有列表为空."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = await discover_workspace(
                action="discover",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            assert result["data"]["investors"] == []
            assert result["data"]["portfolios"] == []

    @pytest.mark.asyncio
    async def test_default_workspace_on_missing_deps(self):
        """_deps 缺失时使用默认路径."""
        result = await discover_workspace(action="discover")
        assert "success" in result


class TestInit:
    """init 测试."""

    @pytest.mark.asyncio
    async def test_init_creates_dirs(self):
        """init 创建目录和 profile.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = await discover_workspace(
                action="init",
                investor_name="test_trader",
                capital=200000.0,
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            assert result["data"]["investor_name"] == "test_trader"
            assert result["data"]["capital"] == 200000.0

            assert (root / "config" / "investors" / "test_trader").is_dir()
            assert (root / "config" / "portfolios").is_dir()
            assert (root / "data").is_dir()

            profile_path = root / "config" / "investors" / "test_trader" / "profile.yaml"
            assert profile_path.is_file()


class TestValidate:
    """validate 测试."""

    @pytest.mark.asyncio
    async def test_validate_missing_files(self):
        """缺少文件 — 返回 missing 列表."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = await discover_workspace(
                action="validate",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is False
            assert "missing" in result["data"]
            assert len(result["data"]["missing"]) > 0


class TestInvalidAction:
    """无效 action 测试."""

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """未知 action → error."""
        result = await discover_workspace(action="foobar")
        assert result["success"] is False
        assert "未知" in result["error"]
