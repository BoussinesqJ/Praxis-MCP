"""策略版本对比测试 — version_compare handler."""
from __future__ import annotations

import tempfile
import yaml
from pathlib import Path

import pytest

from praxis.tools.version_compare import version_compare


def _make_deps(workspace_path=None):
    """构造 _deps 字典."""
    return {"workspace": workspace_path or "."}


_BASE_STRATEGY = {
    "name": "grid_value",
    "version": "1.0.0",
    "description": "网格价值策略 V1",
    "rules": [
        {"rule_id": "risk.cash_floor", "name": "现金底线", "level": "hard_block", "enabled": True},
        {"rule_id": "position.single_cap", "name": "单标的上限", "level": "hard_block", "enabled": True,
         "params": {"max_pct": 30.0}},
    ],
    "ai_teams": [
        {"team_name": "valuation", "members": []},
        {"team_name": "risk", "members": []},
    ],
    "suitable_for": ["A股"],
    "evolution_dimensions": ["risk"],
}


def _write_version(root, strategy_name, version, data):
    """写入一个策略版本 YAML 文件."""
    versions_dir = root / "config" / "strategies" / "versions" / strategy_name
    versions_dir.mkdir(parents=True, exist_ok=True)
    filepath = versions_dir / f"{version}.yaml"
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


class TestDiff:
    """diff 对比."""

    @pytest.mark.asyncio
    async def test_diff_basic(self):
        """版本对比 — 参数变更检测."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            data_v1 = dict(_BASE_STRATEGY)
            _write_version(root, "grid_value", "1.0.0", data_v1)

            data_v2 = dict(_BASE_STRATEGY)
            data_v2["version"] = "2.0.0"
            data_v2["description"] = "网格价值策略 V2"
            # 修改参数
            data_v2["rules"] = [
                {"rule_id": "risk.cash_floor", "name": "现金底线", "level": "hard_block", "enabled": True},
                {"rule_id": "position.single_cap", "name": "单标的上限", "level": "hard_block", "enabled": True,
                 "params": {"max_pct": 40.0}},  # 30→40
            ]
            data_v2["ai_teams"] = [
                {"team_name": "valuation", "members": []},
                {"team_name": "risk", "members": []},
            ]
            data_v2["suitable_for"] = ["A股"]
            data_v2["evolution_dimensions"] = ["risk"]
            _write_version(root, "grid_value", "2.0.0", data_v2)

            result = await version_compare(
                action="diff",
                strategy_name="grid_value",
                version_a="1.0.0",
                version_b="2.0.0",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            data = result["data"]
            assert data["strategy_name"] == "grid_value"

            # 参数变更
            param_mods = [m for m in data["modifications"] if m.get("field") == "params"]
            assert len(param_mods) >= 1

            # 版本号变更
            version_mods = [m for m in data["modifications"]
                          if m["section"] == "metadata" and m["item"] == "version"]
            assert len(version_mods) == 1

    @pytest.mark.asyncio
    async def test_diff_additions(self):
        """版本对比 — 新增规则和 team."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            data_v1 = dict(_BASE_STRATEGY)
            _write_version(root, "trend", "1.0.0", data_v1)

            data_v2 = dict(_BASE_STRATEGY)
            data_v2["version"] = "1.1.0"
            # 新增规则
            data_v2["rules"] = [
                {"rule_id": "risk.cash_floor", "name": "现金底线", "level": "hard_block", "enabled": True},
                {"rule_id": "position.single_cap", "name": "单标的上限", "level": "hard_block", "enabled": True,
                 "params": {"max_pct": 30.0}},
                {"rule_id": "risk.stop_loss", "name": "止损线", "level": "hard_block", "enabled": True,
                 "params": {"max_loss_pct": 10.0}},
            ]
            # 新增 team
            data_v2["ai_teams"] = [
                {"team_name": "valuation", "members": []},
                {"team_name": "risk", "members": []},
                {"team_name": "macro", "members": []},
            ]
            data_v2["suitable_for"] = ["A股"]
            data_v2["evolution_dimensions"] = ["risk"]
            _write_version(root, "trend", "1.1.0", data_v2)

            result = await version_compare(
                action="diff",
                strategy_name="trend",
                version_a="1.0.0",
                version_b="1.1.0",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            data = result["data"]
            # 至少有一条新增
            assert len(data["additions"]) >= 1

            rule_adds = [a for a in data["additions"] if a["section"] == "rules"]
            assert len(rule_adds) >= 1
            if rule_adds:
                assert rule_adds[0]["item"] == "risk.stop_loss"

            team_adds = [a for a in data["additions"] if a["section"] == "ai_teams"]
            assert len(team_adds) >= 1

    @pytest.mark.asyncio
    async def test_diff_deletions(self):
        """版本对比 — 删除规则."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            data_v1 = dict(_BASE_STRATEGY)
            _write_version(root, "mean_rev", "1.0.0", data_v1)

            data_v2 = dict(_BASE_STRATEGY)
            data_v2["version"] = "2.0.0"
            # 删除一条规则
            data_v2["rules"] = [
                {"rule_id": "risk.cash_floor", "name": "现金底线", "level": "hard_block", "enabled": True},
            ]
            # 删除一个 team
            data_v2["ai_teams"] = [
                {"team_name": "valuation", "members": []},
            ]
            data_v2["suitable_for"] = ["A股"]
            data_v2["evolution_dimensions"] = ["risk"]
            _write_version(root, "mean_rev", "2.0.0", data_v2)

            result = await version_compare(
                action="diff",
                strategy_name="mean_rev",
                version_a="1.0.0",
                version_b="2.0.0",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            data = result["data"]

            rule_dels = [d for d in data["deletions"] if d["section"] == "rules"]
            assert len(rule_dels) >= 1
            if rule_dels:
                assert rule_dels[0]["item"] == "position.single_cap"

            team_dels = [d for d in data["deletions"] if d["section"] == "ai_teams"]
            assert len(team_dels) >= 1

    @pytest.mark.asyncio
    async def test_diff_no_changes(self):
        """两个版本完全一致 — 无变更."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            data = dict(_BASE_STRATEGY)
            _write_version(root, "stable", "1.0.0", data)
            _write_version(root, "stable", "1.0.1", dict(data))
            # 修改为相同内容（但版本号字段 yaml 已自动 align）

            result = await version_compare(
                action="diff",
                strategy_name="stable",
                version_a="1.0.0",
                version_b="1.0.1",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            # 仅有版本号 meta 变更（description 相同所以不算 modification）
            data_result = result["data"]
            additions = [a for a in data_result["additions"] if a["section"] != "metadata"]
            deletions = [d for d in data_result["deletions"] if d["section"] != "metadata"]
            modifications = [m for m in data_result["modifications"] if m["section"] != "metadata"]
            assert len(additions) == 0
            assert len(deletions) == 0


class TestErrors:
    """错误处理."""

    @pytest.mark.asyncio
    async def test_nonexistent_version(self):
        """不存在的版本 → error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            versions_dir = root / "config" / "strategies" / "versions" / "grid_value"
            versions_dir.mkdir(parents=True)

            result = await version_compare(
                action="diff",
                strategy_name="grid_value",
                version_a="1.0.0",
                version_b="9.9.9",
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is False
            assert "不存在" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_invalid_action(self):
        """无效 action → error."""
        result = await version_compare(
            action="bad_action",
            _deps=_make_deps("."),
        )
        assert result["success"] is False
        assert "未知" in result.get("error", "")
