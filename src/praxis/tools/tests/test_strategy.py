"""策略管理工具测试 — strategy handler."""
from __future__ import annotations

import tempfile
import yaml
from pathlib import Path

import pytest

from praxis.tools.strategy import strategy


def _make_deps(workspace_path=None):
    """构造 _deps 字典."""
    return {"workspace": workspace_path or "."}


_STANDARD_STRATEGY_YAML = {
    "name": "grid_value",
    "version": "1.0.0",
    "description": "网格价值策略",
    "rules": [
        {"rule": "risk.cash_floor", "name": "现金底线", "level": "hard_block", "enabled": True},
        {"rule": "position.single_cap", "name": "单标的上限", "level": "hard_block", "enabled": True},
        {"rule": "risk.stop_loss", "name": "止损线", "level": "hard_block", "enabled": True,
         "params": {"max_loss_pct": 10.0}},
    ],
    "ai_teams": {
        "valuation": {"preferred_masters": []},
        "risk": {"preferred_masters": []},
    },
    "suitable_for": ["A股", "港股"],
    "evolution_dimensions": ["risk", "position"],
}


class TestList:
    """列出策略."""

    @pytest.mark.asyncio
    async def test_list_strategies(self):
        """列出所有 .yaml 策略文件."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            strategies_dir = root / "config" / "strategies"
            strategies_dir.mkdir(parents=True)

            # 创建 3 个策略文件
            for name in ["grid_value", "trend_following", "mean_reversion"]:
                filepath = strategies_dir / f"{name}.yaml"
                filepath.write_text("name: test", encoding="utf-8")

            result = await strategy(action="list", _deps=_make_deps(str(root)))
            assert result["success"] is True
            assert result["data"]["count"] == 3
            assert "grid_value" in result["data"]["strategies"]
            assert "trend_following" in result["data"]["strategies"]

    @pytest.mark.asyncio
    async def test_list_empty(self):
        """空目录 — 返回空列表."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            strategies_dir = root / "config" / "strategies"
            strategies_dir.mkdir(parents=True)

            result = await strategy(action="list", _deps=_make_deps(str(root)))
            assert result["success"] is True
            assert result["data"]["strategies"] == []
            assert result["data"]["count"] == 0


class TestInfo:
    """策略详情."""

    @pytest.mark.asyncio
    async def test_info_strategy(self):
        """查询已有策略详情."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            strategies_dir = root / "config" / "strategies"
            strategies_dir.mkdir(parents=True)

            filepath = strategies_dir / "grid_value.yaml"
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(_STANDARD_STRATEGY_YAML, f, allow_unicode=True, default_flow_style=False)

            result = await strategy(
                action="info", strategy_name="grid_value",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            assert result["data"]["strategy_name"] == "grid_value"
            assert result["data"]["version"] == "1.0.0"
            assert len(result["data"]["rules"]) == 3
            assert len(result["data"]["ai_teams"]) == 2

    @pytest.mark.asyncio
    async def test_info_nonexistent(self):
        """查询不存在的策略 → error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            strategies_dir = root / "config" / "strategies"
            strategies_dir.mkdir(parents=True)

            result = await strategy(
                action="info", strategy_name="nonexistent_strategy",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is False
            assert "不存在" in result.get("error", "")


class TestVersions:
    """版本历史."""

    @pytest.mark.asyncio
    async def test_versions(self):
        """策略版本列表."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            versions_dir = root / "config" / "strategies" / "versions" / "grid_value"
            versions_dir.mkdir(parents=True)

            for ver in ["1.0.0", "1.1.0", "2.0.0"]:
                (versions_dir / f"{ver}.yaml").write_text("version: " + ver, encoding="utf-8")

            result = await strategy(
                action="versions", strategy_name="grid_value",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            assert result["data"]["strategy_name"] == "grid_value"
            assert len(result["data"]["versions"]) == 3
            versions = [v["version"] for v in result["data"]["versions"]]
            assert "1.0.0" in versions

    @pytest.mark.asyncio
    async def test_versions_empty(self):
        """无版本历史 → 返回空列表."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            versions_dir = root / "config" / "strategies" / "versions" / "new_strategy"
            versions_dir.mkdir(parents=True)

            result = await strategy(
                action="versions", strategy_name="new_strategy",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            assert result["data"]["versions"] == []


class TestInvalidAction:
    """无效 action."""

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """未知 action → error."""
        result = await strategy(action="foobar", _deps=_make_deps("."))
        assert result["success"] is False
        assert "未知" in result["error"]
