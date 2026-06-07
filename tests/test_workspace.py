"""Tests for discover_workspace_tool — workspace auto-discovery"""
import json
import pytest
from pathlib import Path

import yaml

from praxis.tools.workspace import (
    discover_workspace,
    _load_yaml_safe,
    _scan_investors,
    _scan_ledger,
    _scan_nav,
    _scan_strategies,
    _generate_quick_start,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ws(tmp_path):
    """Create a minimal workspace skeleton."""
    return tmp_path


@pytest.fixture
def ws_with_investor(ws):
    """Workspace with one investor + one portfolio."""
    inv_dir = ws / "investors" / "example" / "portfolios" / "demo"
    inv_dir.mkdir(parents=True)

    profile = {
        "investor": {
            "name": "示例投资者",
            "risk_level": "C3",
            "capital_cny": 100000.0,
        }
    }
    (ws / "investors" / "example" / "profile.yaml").write_text(
        yaml.dump(profile, allow_unicode=True), encoding="utf-8"
    )

    portfolio = {
        "portfolio": {
            "strategy_type": "grid_value",
            "description": "网格价值策略",
        },
        "assets": [
            {"ticker": "016874", "name": "广发远见智选C", "type": "offshore_fund"},
            {"ticker": "600995", "name": "南网储能", "type": "stock"},
            {"ticker": "510310", "name": "沪深300ETF", "type": "etf"},
            {"ticker": "589850", "name": "科创50ETF", "type": "etf"},
        ],
    }
    (inv_dir / "portfolio.yaml").write_text(
        yaml.dump(portfolio, allow_unicode=True), encoding="utf-8"
    )
    return ws


@pytest.fixture
def ws_with_ledger(ws_with_investor):
    """Workspace with investor + ledger data."""
    ledger_dir = ws_with_investor / "data" / "ledger"
    ledger_dir.mkdir(parents=True)

    records = [
        {
            "tx_id": "tx-20260606-001",
            "type": "buy",
            "ticker": "600995",
            "quantity": 100,
            "price": 14.318,
            "status": "confirmed",
            "tags": ["real"],
            "created_at": "2026-06-06T10:00:00",
        },
        {
            "tx_id": "tx-20260606-002",
            "type": "buy",
            "ticker": "510310",
            "quantity": 400,
            "price": 4.826,
            "status": "confirmed",
            "tags": ["real"],
            "created_at": "2026-06-06T10:01:00",
        },
        {
            "tx_id": "tx-20260606-003",
            "type": "buy",
            "ticker": "589850",
            "quantity": 1875,
            "price": 1.600,
            "status": "confirmed",
            "tags": ["opening"],
            "created_at": "2026-06-06T10:02:00",
        },
        {
            "tx_id": "tx-20260606-pending-001",
            "type": "buy",
            "ticker": "016874",
            "quantity": 500,
            "price": 1.95,
            "status": "pending",
            "created_at": "2026-06-06T10:03:00",
        },
    ]

    with open(ledger_dir / "transactions.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return ws_with_investor


@pytest.fixture
def ws_full(ws_with_ledger):
    """Workspace with investor + ledger + nav + strategies."""
    # NAV history
    nav_dir = ws_with_ledger / "data" / "nav"
    nav_dir.mkdir(parents=True)
    nav_records = [
        {"date": "2026-06-06", "nav": 1.0, "total_assets": 70852.05},
        {"date": "2026-06-07", "nav": 1.002, "total_assets": 70993.95},
    ]
    with open(nav_dir / "default.jsonl", "w", encoding="utf-8") as f:
        for r in nav_records:
            f.write(json.dumps(r) + "\n")

    # Strategies
    strategies_dir = ws_with_ledger / "strategies"
    strategies_dir.mkdir(parents=True)
    (strategies_dir / "grid_value.yaml").write_text("name: grid_value\n", encoding="utf-8")
    (strategies_dir / "momentum.yml").write_text("name: momentum\n", encoding="utf-8")
    # Hidden file should be ignored
    (strategies_dir / "_draft.yaml").write_text("draft", encoding="utf-8")

    return ws_with_ledger


# ---------------------------------------------------------------------------
# Test: Empty workspace
# ---------------------------------------------------------------------------

class TestEmptyWorkspace:
    """discover_workspace on a completely empty directory."""

    def test_success(self, ws):
        result = discover_workspace(str(ws))
        assert result["success"] is True

    def test_is_not_initialized(self, ws):
        data = discover_workspace(str(ws))["data"]
        assert data["is_initialized"] is False

    def test_empty_investors(self, ws):
        data = discover_workspace(str(ws))["data"]
        assert data["investors"] == []

    def test_empty_ledger(self, ws):
        data = discover_workspace(str(ws))["data"]
        assert data["ledger"]["total_records"] == 0
        assert data["ledger"]["confirmed"] == 0
        assert data["ledger"]["pending"] == 0
        assert data["ledger"]["unique_tickers"] == []

    def test_empty_strategies(self, ws):
        data = discover_workspace(str(ws))["data"]
        assert data["strategies"] == []

    def test_no_nav(self, ws):
        data = discover_workspace(str(ws))["data"]
        assert data["nav_history"]["record_count"] == 0
        assert data["nav_history"]["latest_date"] is None

    def test_quick_start_suggests_init(self, ws):
        data = discover_workspace(str(ws))["data"]
        calls = data["quick_start"]["recommended_calls"]
        assert len(calls) == 1
        assert "init_investor_tool" in calls[0]

    def test_no_warnings(self, ws):
        data = discover_workspace(str(ws))["data"]
        assert data["warnings"] == []


# ---------------------------------------------------------------------------
# Test: Single investor + portfolio
# ---------------------------------------------------------------------------

class TestSingleInvestor:
    """discover_workspace with one investor and one portfolio."""

    def test_is_initialized(self, ws_with_investor):
        data = discover_workspace(str(ws_with_investor))["data"]
        assert data["is_initialized"] is True

    def test_investor_count(self, ws_with_investor):
        data = discover_workspace(str(ws_with_investor))["data"]
        assert len(data["investors"]) == 1

    def test_investor_id(self, ws_with_investor):
        inv = discover_workspace(str(ws_with_investor))["data"]["investors"][0]
        assert inv["id"] == "example"

    def test_investor_name(self, ws_with_investor):
        inv = discover_workspace(str(ws_with_investor))["data"]["investors"][0]
        assert inv["name"] == "示例投资者"

    def test_investor_risk_level(self, ws_with_investor):
        inv = discover_workspace(str(ws_with_investor))["data"]["investors"][0]
        assert inv["risk_level"] == "C3"

    def test_portfolio_count(self, ws_with_investor):
        inv = discover_workspace(str(ws_with_investor))["data"]["investors"][0]
        assert len(inv["portfolios"]) == 1

    def test_portfolio_id(self, ws_with_investor):
        port = discover_workspace(str(ws_with_investor))["data"]["investors"][0]["portfolios"][0]
        assert port["id"] == "demo"

    def test_portfolio_strategy(self, ws_with_investor):
        port = discover_workspace(str(ws_with_investor))["data"]["investors"][0]["portfolios"][0]
        assert port["strategy"] == "grid_value"

    def test_portfolio_tickers(self, ws_with_investor):
        port = discover_workspace(str(ws_with_investor))["data"]["investors"][0]["portfolios"][0]
        assert port["asset_count"] == 4
        assert set(port["tickers"]) == {"016874", "600995", "510310", "589850"}


# ---------------------------------------------------------------------------
# Test: Ledger scanning
# ---------------------------------------------------------------------------

class TestLedgerScanning:
    """Ledger statistics from transactions.jsonl."""

    def test_total_records(self, ws_with_ledger):
        ledger = discover_workspace(str(ws_with_ledger))["data"]["ledger"]
        assert ledger["total_records"] == 4

    def test_confirmed_count(self, ws_with_ledger):
        ledger = discover_workspace(str(ws_with_ledger))["data"]["ledger"]
        assert ledger["confirmed"] == 3

    def test_pending_count(self, ws_with_ledger):
        ledger = discover_workspace(str(ws_with_ledger))["data"]["ledger"]
        assert ledger["pending"] == 1

    def test_unique_tickers(self, ws_with_ledger):
        ledger = discover_workspace(str(ws_with_ledger))["data"]["ledger"]
        assert set(ledger["unique_tickers"]) == {"016874", "600995", "510310", "589850"}

    def test_corrupt_line_warning(self, ws_with_investor):
        """Corrupt JSONL lines should be skipped with a warning."""
        ledger_dir = ws_with_investor / "data" / "ledger"
        ledger_dir.mkdir(parents=True)
        with open(ledger_dir / "transactions.jsonl", "w", encoding="utf-8") as f:
            f.write('{"tx_id": "tx-001", "ticker": "600995", "status": "confirmed"}\n')
            f.write("NOT VALID JSON\n")
            f.write('{"tx_id": "tx-002", "ticker": "510310", "status": "confirmed"}\n')

        data = discover_workspace(str(ws_with_investor))["data"]
        assert data["ledger"]["total_records"] == 2
        assert len(data["warnings"]) >= 1
        assert any("corrupt" in w for w in data["warnings"])


# ---------------------------------------------------------------------------
# Test: NAV history scanning
# ---------------------------------------------------------------------------

class TestNavScanning:
    """NAV history scanning."""

    def test_record_count(self, ws_full):
        nav = discover_workspace(str(ws_full))["data"]["nav_history"]
        assert nav["record_count"] == 2

    def test_latest_date(self, ws_full):
        nav = discover_workspace(str(ws_full))["data"]["nav_history"]
        assert nav["latest_date"] == "2026-06-07"

    def test_no_nav_dir(self, ws_with_investor):
        nav = discover_workspace(str(ws_with_investor))["data"]["nav_history"]
        assert nav["record_count"] == 0
        assert nav["latest_date"] is None


# ---------------------------------------------------------------------------
# Test: Strategy scanning
# ---------------------------------------------------------------------------

class TestStrategyScanning:
    """Strategy directory scanning."""

    def test_finds_yaml_and_yml(self, ws_full):
        strategies = discover_workspace(str(ws_full))["data"]["strategies"]
        assert "grid_value" in strategies
        assert "momentum" in strategies

    def test_ignores_hidden_files(self, ws_full):
        strategies = discover_workspace(str(ws_full))["data"]["strategies"]
        assert "_draft" not in strategies

    def test_sorted(self, ws_full):
        strategies = discover_workspace(str(ws_full))["data"]["strategies"]
        assert strategies == sorted(strategies)


# ---------------------------------------------------------------------------
# Test: Data freshness
# ---------------------------------------------------------------------------

class TestDataFreshness:
    """Data freshness / staleness detection."""

    def test_latest_transaction(self, ws_with_ledger):
        freshness = discover_workspace(str(ws_with_ledger))["data"]["data_freshness"]
        assert freshness["latest_transaction"] == "2026-06-06"

    def test_stale_days_is_int(self, ws_with_ledger):
        freshness = discover_workspace(str(ws_with_ledger))["data"]["data_freshness"]
        assert isinstance(freshness["stale_days"], int)
        assert freshness["stale_days"] >= 0

    def test_latest_nav(self, ws_full):
        freshness = discover_workspace(str(ws_full))["data"]["data_freshness"]
        assert freshness["latest_nav"] == "2026-06-07"


# ---------------------------------------------------------------------------
# Test: Quick start generation
# ---------------------------------------------------------------------------

class TestQuickStart:
    """Quick start recommendations."""

    def test_recommends_summary_and_performance(self, ws_with_investor):
        calls = discover_workspace(str(ws_with_investor))["data"]["quick_start"]["recommended_calls"]
        assert any("get_portfolio_summary_tool" in c for c in calls)
        assert any("get_performance_tool" in c for c in calls)

    def test_uses_correct_ids(self, ws_with_investor):
        calls = discover_workspace(str(ws_with_investor))["data"]["quick_start"]["recommended_calls"]
        for c in calls:
            assert "example" in c
            assert "demo" in c

    def test_excludes_migration_tags(self, ws_with_ledger):
        """When ledger has 'opening' tags, quick start should recommend exclude_tags."""
        calls = discover_workspace(str(ws_with_ledger))["data"]["quick_start"]["recommended_calls"]
        perf_call = [c for c in calls if "get_performance_tool" in c]
        assert len(perf_call) == 1
        assert "exclude_tags" in perf_call[0]
        assert "opening" in perf_call[0]

    def test_no_nav_suggests_record_nav(self, ws_with_investor):
        """When no NAV history exists, suggest recording NAV."""
        calls = discover_workspace(str(ws_with_investor))["data"]["quick_start"]["recommended_calls"]
        assert any("record_nav_tool" in c for c in calls)


# ---------------------------------------------------------------------------
# Test: Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case handling."""

    def test_corrupt_yaml_skipped_with_warning(self, ws):
        """Corrupt profile.yaml should be skipped and added to warnings."""
        inv_dir = ws / "investors" / "bad_investor"
        inv_dir.mkdir(parents=True)
        (inv_dir / "profile.yaml").write_text("{{invalid yaml", encoding="utf-8")

        data = discover_workspace(str(ws))["data"]
        assert len(data["investors"]) == 0
        assert len(data["warnings"]) >= 1

    def test_investor_dir_without_profile_skipped(self, ws):
        """Investor directory without profile.yaml should be skipped."""
        (ws / "investors" / "no_profile").mkdir(parents=True)
        data = discover_workspace(str(ws))["data"]
        assert len(data["investors"]) == 0

    def test_hidden_directories_skipped(self, ws):
        """Directories starting with _ or . should be skipped."""
        (ws / "investors" / "_hidden").mkdir(parents=True)
        (ws / "investors" / ".git").mkdir(parents=True)
        data = discover_workspace(str(ws))["data"]
        assert len(data["investors"]) == 0

    def test_workspace_path_in_output(self, ws_with_investor):
        """Output should contain absolute workspace path."""
        data = discover_workspace(str(ws_with_investor))["data"]
        assert Path(data["workspace"]).is_absolute()


# ---------------------------------------------------------------------------
# Test: Full integration
# ---------------------------------------------------------------------------

class TestFullIntegration:
    """Full integration test with all data present."""

    def test_full_discovery(self, ws_full):
        result = discover_workspace(str(ws_full))
        assert result["success"] is True

        data = result["data"]
        assert data["is_initialized"] is True
        assert len(data["investors"]) == 1
        assert data["investors"][0]["id"] == "example"
        assert data["investors"][0]["portfolios"][0]["id"] == "demo"
        assert len(data["investors"][0]["portfolios"][0]["tickers"]) == 4
        assert data["ledger"]["total_records"] == 4
        assert data["ledger"]["confirmed"] == 3
        assert data["ledger"]["pending"] == 1
        assert data["nav_history"]["record_count"] == 2
        assert len(data["strategies"]) == 2
        assert data["data_freshness"]["latest_transaction"] == "2026-06-06"
        assert data["data_freshness"]["latest_nav"] == "2026-06-07"
        assert len(data["quick_start"]["recommended_calls"]) >= 2
        assert isinstance(data["warnings"], list)

    def test_exception_returns_error(self, monkeypatch):
        """Unhandled exceptions should return success=False."""
        def boom(*args, **kwargs):
            raise RuntimeError("disk failure")

        monkeypatch.setattr("praxis.tools.workspace._scan_investors", boom)
        result = discover_workspace("/nonexistent")
        # _scan_investors raising should be caught by the outer try/except
        # but since it's inside the try, it should produce an error result
        # However, Path() won't fail for /nonexistent, only _scan_investors will
        assert result["success"] is False
        assert "disk failure" in result["error"]
