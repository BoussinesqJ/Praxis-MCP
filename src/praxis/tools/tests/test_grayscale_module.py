"""灰度工具测试 — grayscale 函数."""
from __future__ import annotations

import pytest

from praxis.tools.grayscale import grayscale
from praxis.engine.tests.conftest import FakeLedger
from praxis.core.models import (
    Transaction, TransactionType, TransactionStatus, AssetType,
)


@pytest.fixture
def workspace_with_strategy(tmp_path):
    """创建含策略 YAML 的工作区."""
    strategies_dir = tmp_path / "config" / "strategies"
    strategies_dir.mkdir(parents=True)

    content = """
name: grid_value
description: 网格价值策略
"""
    (strategies_dir / "grid_value.yaml").write_text(content, encoding="utf-8")
    return str(tmp_path)


def _make_ledger():
    return FakeLedger([
        Transaction(
            ticker="600519", tx_type=TransactionType.BUY,
            quantity=100.0, price=1800.0, fee=5.0,
            asset_type=AssetType.STOCK,
            status=TransactionStatus.EXECUTED,
            created_at="2024-06-15T10:00:00",
        ),
    ])


def _make_deps(workspace, ledger=None, benchmark_provider=None):
    return {
        "workspace": workspace,
        "ledger": ledger,
        "benchmark_provider": benchmark_provider,
    }


class TestValidateRouting:
    """validate 工具路由."""

    @pytest.mark.asyncio
    async def test_validate(self, workspace_with_strategy):
        """validate 返回灰度验证结果."""
        deps = _make_deps(workspace_with_strategy, ledger=_make_ledger())

        result = await grayscale(
            action="validate",
            strategy_name="grid_value",
            change_description="调整参数",
            risk_level="medium",
            _deps=deps,
        )
        assert result["success"] is True
        data = result["data"]
        assert data["strategy_name"] == "grid_value"
        assert "validation_passed" in data
        assert "backup_path" in data


class TestStatusRouting:
    """status 工具路由."""

    @pytest.mark.asyncio
    async def test_status(self, workspace_with_strategy):
        """status 返回灰度状态."""
        result = await grayscale(
            action="status",
            strategy_name="grid_value",
            _deps={"workspace": workspace_with_strategy},
        )
        assert result["success"] is True
        assert result["data"]["strategy_name"] == "grid_value"
        assert "strategy_exists" in result["data"]
        assert "backup_count" in result["data"]


class TestMissingDeps:
    """_deps 缺必要组件."""

    @pytest.mark.asyncio
    async def test_missing_ledger(self, workspace_with_strategy):
        """validate 需要 loger — 没有 loger 也能跑（只有回测失败）."""
        result = await grayscale(
            action="validate",
            strategy_name="grid_value",
            change_description="测试",
            risk_level="low",
            _deps={"workspace": workspace_with_strategy},
        )
        # low risk 不需要回测，可以成功
        assert result["success"] is True


class TestInvalidAction:
    """非法 action."""

    @pytest.mark.asyncio
    async def test_invalid_action(self, workspace_with_strategy):
        """非法 action → error."""
        result = await grayscale(
            action="invalid",
            strategy_name="grid_value",
            _deps={"workspace": workspace_with_strategy},
        )
        assert result["success"] is False
        assert "未知" in result["error"]


class TestInvalidRiskLevel:
    """参数校验 — 无效 risk_level."""

    @pytest.mark.asyncio
    async def test_invalid_risk_level(self, workspace_with_strategy):
        """无效 risk_level → error."""
        result = await grayscale(
            action="validate",
            strategy_name="grid_value",
            risk_level="extreme",
            _deps={"workspace": workspace_with_strategy},
        )
        assert result["success"] is False
        assert "无效" in result["error"]


class TestReturnFormat:
    """返回值格式."""

    @pytest.mark.asyncio
    async def test_validate_format(self, workspace_with_strategy):
        """validate 返回标准格式."""
        deps = _make_deps(workspace_with_strategy, ledger=_make_ledger())

        result = await grayscale(
            action="validate",
            strategy_name="grid_value",
            change_description="测试",
            risk_level="medium",
            _deps=deps,
        )
        assert "success" in result
        assert isinstance(result["success"], bool)
        if result["success"]:
            assert "data" in result
        else:
            assert "error" in result

    @pytest.mark.asyncio
    async def test_status_format(self, workspace_with_strategy):
        """status 返回 {success, data, ...}."""
        result = await grayscale(
            action="status",
            strategy_name="grid_value",
            _deps={"workspace": workspace_with_strategy},
        )
        assert "success" in result
        assert "data" in result
        assert "strategy_exists" in result["data"]
        assert "backups" in result["data"]
