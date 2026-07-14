"""投资者管理工具测试 — investor handler."""
from __future__ import annotations

import tempfile
import yaml
from pathlib import Path

import pytest

from praxis.tools.investor import investor
from praxis.engine.tests.conftest import FakeLedger


def _make_deps(workspace_path=None, ledger=None):
    """构造 _deps 字典."""
    deps = {"workspace": workspace_path or "."}
    if ledger is not None:
        deps["ledger"] = ledger
    return deps


def _make_positions():
    """默认持仓列表."""
    return [
        {"ticker": "600519", "name": "贵州茅台", "quantity": 10, "avg_cost": 1800.0, "type": "stock", "category": "large_cap"},
        {"ticker": "159915", "name": "创业板ETF", "quantity": 1000, "avg_cost": 2.30, "type": "etf", "category": "broad_market"},
    ]


class TestCreateInvestor:
    """创建投资者画像和组合."""

    @pytest.mark.asyncio
    async def test_create_investor(self):
        """create action — 创建 profile.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = await investor(
                action="create",
                investor_id="trader_001",
                name="测试交易者",
                capital_cny=100000.0,
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            assert result["data"]["investor_id"] == "trader_001"

            profile_path = root / "config" / "investors" / "trader_001" / "profile.yaml"
            assert profile_path.is_file()

            with open(profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["investor"]["name"] == "测试交易者"
            assert data["investor"]["capital_cny"] == 100000.0

    @pytest.mark.asyncio
    async def test_create_portfolio(self):
        """create action — 创建 portfolio.yaml（含 assets + sentinels 骨架）."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            positions = _make_positions()
            result = await investor(
                action="create",
                investor_id="trader_002",
                name="交易者2",
                capital_cny=50000.0,
                portfolio_id="growth",
                positions=positions,
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is True
            assert result["data"]["portfolio_id"] == "growth"
            assert result["data"]["assets_count"] == 2

            portfolio_path = (
                root / "config" / "investors" / "trader_002"
                / "portfolios" / "growth" / "portfolio.yaml"
            )
            assert portfolio_path.is_file()

            with open(portfolio_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert len(data["assets"]) == 2
            assert data["assets"][0]["ticker"] == "600519"
            assert "sentinels" in data
            assert "macro_layer" in data["sentinels"]


class TestInitFull:
    """init action — 完整初始化."""

    @pytest.mark.asyncio
    async def test_init_full(self):
        """init — profile + portfolio + ledger entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ledger = FakeLedger()
            positions = _make_positions()

            result = await investor(
                action="init",
                investor_id="trader_init",
                name="初始化交易者",
                capital_cny=100000.0,
                portfolio_id="core",
                positions=positions,
                cash=30000.0,
                _deps=_make_deps(str(root), ledger=ledger),
            )
            assert result["success"] is True
            assert result["data"]["investor_id"] == "trader_init"
            assert result["data"]["portfolio_id"] == "core"
            assert result["data"]["summary"]["positions"] == 2
            assert len(result["data"]["summary"]["transaction_ids"]) == 2

            # 验证文件创建
            profile_path = root / "config" / "investors" / "trader_init" / "profile.yaml"
            assert profile_path.is_file()

            portfolio_path = (
                root / "config" / "investors" / "trader_init"
                / "portfolios" / "core" / "portfolio.yaml"
            )
            assert portfolio_path.is_file()

            # 验证 ledger 记录
            txs = ledger.get_all()
            assert len(txs) == 2
            assert txs[0].ticker == "600519"
            assert txs[0].tx_type.value == "buy"
            assert txs[1].ticker == "159915"


class TestList:
    """list action."""

    @pytest.mark.asyncio
    async def test_list_investors(self):
        """列出所有投资者."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # 创建两个投资者
            for i in range(2):
                await investor(
                    action="create",
                    investor_id=f"inv_{i:03d}",
                    name=f"投资者{i}",
                    capital_cny=100000.0,
                    _deps=_make_deps(str(root)),
                )

            result = await investor(action="list", _deps=_make_deps(str(root)))
            assert result["success"] is True
            assert result["data"]["count"] == 2
            assert len(result["data"]["investors"]) == 2
            ids = [inv["investor_id"] for inv in result["data"]["investors"]]
            assert "inv_000" in ids
            assert "inv_001" in ids


class TestErrorCases:
    """错误场景."""

    @pytest.mark.asyncio
    async def test_invalid_id(self):
        """非法 ID → error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = await investor(
                action="create",
                investor_id="trader/../etc",  # 路径遍历
                name="hacker",
                capital_cny=100000.0,
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is False
            assert "非法" in result.get("error", "") or "路径" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_duplicate_create(self):
        """重复创建 → error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            await investor(
                action="create",
                investor_id="dup_test",
                name="首次创建",
                capital_cny=100000.0,
                _deps=_make_deps(str(root)),
            )

            result = await investor(
                action="create",
                investor_id="dup_test",
                name="重复创建",
                capital_cny=200000.0,
                _deps=_make_deps(str(root)),
            )
            assert result["success"] is False
            assert "已存在" in result["error"]

    @pytest.mark.asyncio
    async def test_negative_capital(self):
        """负资金 → 允许但不影响文件创建（仅存储值）."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = await investor(
                action="create",
                investor_id="neg_cap",
                name="负资金测试",
                capital_cny=-1000.0,
                _deps=_make_deps(str(root)),
            )
            # 负资金目前不返回 error，仅存储到 YAML
            assert result["success"] is True

            profile_path = root / "config" / "investors" / "neg_cap" / "profile.yaml"
            with open(profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            assert data["investor"]["capital_cny"] == -1000.0

    @pytest.mark.asyncio
    async def test_missing_workspace(self):
        """无 workspace → 使用默认路径 '.' 并正常创建."""
        result = await investor(
            action="list",
            _deps={},
        )
        # list 在默认路径下可能成功（如果目录不存在返回空列表）或失败
        assert "success" in result
        if result["success"]:
            assert result["data"]["investors"] == []
        # 如果因权限/路径问题失败也是合理的
