# Design Spec: discover_workspace_tool

> **Date**: 2026-06-06
> **Status**: Approved for implementation
> **Scope**: Praxis MCP Server — workspace auto-discovery
> **Target repo**: `<WORKSPACE>`

---

## Problem Statement

When an AI agent connects to Praxis MCP for the first time, it enters a "blind" state — it doesn't know:

- What investors exist in the workspace
- What portfolios each investor has
- What transactions are in the ledger
- What the current portfolio state is
- Which tools to call first, and with what parameters

This caused a real incident where the agent called tools with wrong IDs (`"示例投资者"/"main"` instead of `"example"/"demo"`), leading to 16 wasted tool calls and incorrect performance metrics.

## Solution

Add a single zero-parameter tool: `discover_workspace_tool()`. One call returns a complete map of the workspace, enabling the agent to orient itself before making any other calls.

## Data Structure

```json
{
  "workspace": "/path/to/Portfolio vault",
  "is_initialized": true,
  "investors": [
    {
      "id": "example",
      "name": "示例投资者",
      "risk_level": "C3",
      "capital_cny": 100000,
      "portfolios": [
        {
          "id": "demo",
          "strategy": "grid_value",
          "asset_count": 4,
          "tickers": ["016874", "600995", "510310", "589850"]
        }
      ]
    }
  ],
  "ledger": {
    "total_records": 4,
    "confirmed": 4,
    "pending": 0,
    "unique_tickers": ["016874", "600995", "510310", "589850"]
  },
  "nav_history": {
    "record_count": 0,
    "latest_date": null
  },
  "strategies": ["grid_value"],
  "data_freshness": {
    "latest_transaction": "2026-06-06",
    "latest_nav": null,
    "stale_days": null
  },
  "quick_start": {
    "recommended_calls": [
      "get_portfolio_summary_tool(investor='example', portfolio='demo')",
      "get_performance_tool(investor='example', portfolio='demo', exclude_tags=['opening','migration'])"
    ]
  },
  "warnings": []
}
```

### Field Descriptions

| Field | Type | Description |
|:---|:---|:---|
| `workspace` | string | Absolute path to the workspace root |
| `is_initialized` | bool | True if at least one investor exists |
| `investors` | list | Each investor with their portfolios |
| `ledger` | object | Transaction statistics |
| `nav_history` | object | NAV record count and latest date |
| `strategies` | list[str] | Available strategy template names |
| `data_freshness` | object | Timestamps of latest data for staleness detection |
| `quick_start` | object | Recommended next tool calls based on current state |
| `warnings` | list[str] | Non-fatal issues (corrupt files, parse errors) |

## Implementation

### Files to Change

| File | Action | Lines |
|:---|:---|:---|
| `praxis/tools/workspace.py` | **Create** | ~80 lines |
| `praxis/mcp_server.py` | **Modify** | +4 lines (import + tool registration) |

### Core Logic (`praxis/tools/workspace.py`)

```python
"""MCP Tool — Workspace Discovery"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml


def _load_yaml_safe(path: Path, warnings: list[str], context: str) -> dict | None:
    """Load YAML with graceful failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if data else None
    except Exception as e:
        warnings.append(f"{context}: {e}")
        return None


def _scan_investors(ws: Path, warnings: list[str]) -> list[dict]:
    """Scan investors/ directory for profile.yaml + portfolio.yaml."""
    investors = []
    investors_dir = ws / "investors"
    if not investors_dir.exists():
        return investors

    for d in sorted(investors_dir.iterdir()):
        if not d.is_dir() or d.name.startswith(("_", ".")):
            continue
        profile_path = d / "profile.yaml"
        if not profile_path.exists():
            continue

        data = _load_yaml_safe(profile_path, warnings, f"investor '{d.name}'")
        if not data:
            continue

        inv_data = data.get("investor", data)
        investor = {
            "id": d.name,
            "name": inv_data.get("name", d.name),
            "risk_level": inv_data.get("risk_level", "unknown"),
            "capital_cny": inv_data.get("capital_cny", 0),
            "portfolios": [],
        }

        # Scan portfolios
        portfolios_dir = d / "portfolios"
        if portfolios_dir.exists():
            for pd in sorted(portfolios_dir.iterdir()):
                if not pd.is_dir() or pd.name.startswith(("_", ".")):
                    continue
                p_path = pd / "portfolio.yaml"
                if not p_path.exists():
                    continue
                p_data = _load_yaml_safe(p_path, warnings, f"portfolio '{pd.name}'")
                if not p_data:
                    continue
                pdata = p_data.get("portfolio", p_data)
                assets = p_data.get("assets", [])
                investor["portfolios"].append({
                    "id": pd.name,
                    "strategy": pdata.get("strategy_type", "unknown"),
                    "asset_count": len(assets),
                    "tickers": [a.get("ticker", "") for a in assets if a.get("ticker")],
                })

        investors.append(investor)
    return investors


def _scan_ledger(ws: Path, warnings: list[str]) -> dict:
    """Scan transactions.jsonl for stats."""
    ledger_path = ws / "data" / "ledger" / "transactions.jsonl"
    if not ledger_path.exists():
        return {"total_records": 0, "confirmed": 0, "pending": 0, "unique_tickers": []}

    total = confirmed = pending = 0
    tickers = set()
    latest_date = None

    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                total += 1
                if rec.get("status") == "confirmed":
                    confirmed += 1
                elif rec.get("status") == "pending":
                    pending += 1
                tickers.add(rec.get("ticker", ""))
                created = rec.get("created_at", "")
                if created:
                    date_str = created[:10]
                    if latest_date is None or date_str > latest_date:
                        latest_date = date_str
            except (json.JSONDecodeError, Exception):
                warnings.append(f"ledger: corrupt line #{total + 1}, skipped")

    return {
        "total_records": total,
        "confirmed": confirmed,
        "pending": pending,
        "unique_tickers": sorted(tickers),
        "latest_transaction": latest_date,
    }


def _scan_nav(ws: Path) -> dict:
    """Scan nav history."""
    nav_path = ws / "data" / "nav" / "default.jsonl"
    if not nav_path.exists():
        return {"record_count": 0, "latest_date": None}

    count = 0
    latest = None
    with open(nav_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            count += 1
            try:
                rec = json.loads(line)
                d = rec.get("date", "")
                if d and (latest is None or d > latest):
                    latest = d
            except Exception:
                pass

    return {"record_count": count, "latest_date": latest}


def _scan_strategies(ws: Path) -> list[str]:
    """Scan strategies/ directory."""
    strategies_dir = ws / "strategies"
    if not strategies_dir.exists():
        return []
    return sorted(
        f.stem for f in strategies_dir.iterdir()
        if f.suffix in (".yaml", ".yml") and not f.name.startswith(("_", "."))
    )


def _generate_quick_start(investors: list, ledger: dict, nav: dict) -> dict:
    """Generate recommended next calls based on current state."""
    calls = []

    if investors and investors[0].get("portfolios"):
        inv = investors[0]["id"]
        port = investors[0]["portfolios"][0]["id"]
        calls.append(f"get_portfolio_summary_tool(investor='{inv}', portfolio='{port}')")

        has_migration = any("opening" in t or "migration" in t
                           for t in ledger.get("tags_seen", []))
        if has_migration:
            calls.append(
                f"get_performance_tool(investor='{inv}', portfolio='{port}', "
                f"exclude_tags=['opening','migration'])"
            )
        else:
            calls.append(f"get_performance_tool(investor='{inv}', portfolio='{port}')")

        if nav.get("record_count", 0) == 0:
            calls.append(
                f"record_nav_tool(investor='{inv}', portfolio='{port}', "
                f"nav=1.0, total_assets=0, positions_value=0, cash=0)"
            )
    else:
        calls.append("init_investor_tool(investor_id='...', ...) — start by creating an investor")

    return {"recommended_calls": calls}


def discover_workspace(workspace: str = ".") -> dict:
    """Discover workspace state — zero parameters required."""
    try:
        ws = Path(workspace)
        warnings = []

        investors = _scan_investors(ws, warnings)
        ledger = _scan_ledger(ws, warnings)
        nav = _scan_nav(ws)
        strategies = _scan_strategies(ws)
        quick_start = _generate_quick_start(investors, ledger, nav)

        # Data freshness
        today = datetime.now().strftime("%Y-%m-%d")
        latest_tx = ledger.get("latest_transaction")
        latest_nav = nav.get("latest_date")
        stale_days = None
        if latest_tx:
            try:
                stale_days = (datetime.strptime(today, "%Y-%m-%d") -
                              datetime.strptime(latest_tx, "%Y-%m-%d")).days
            except Exception:
                pass

        return {
            "success": True,
            "data": {
                "workspace": str(ws),
                "is_initialized": len(investors) > 0,
                "investors": investors,
                "ledger": {
                    "total_records": ledger["total_records"],
                    "confirmed": ledger["confirmed"],
                    "pending": ledger["pending"],
                    "unique_tickers": ledger["unique_tickers"],
                },
                "nav_history": nav,
                "strategies": strategies,
                "data_freshness": {
                    "latest_transaction": latest_tx,
                    "latest_nav": latest_nav,
                    "stale_days": stale_days,
                },
                "quick_start": quick_start,
                "warnings": warnings,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### MCP Registration (`praxis/mcp_server.py`)

Add to imports:
```python
from praxis.tools.workspace import discover_workspace
```

Add tool (after existing tool registrations):
```python
@mcp.tool()
async def discover_workspace_tool() -> dict:
    """发现 workspace 全景：投资者、组合、持仓、数据状态、推荐下一步操作。
    零参数，首次连接时调用。"""
    return discover_workspace(WORKSPACE)
```

## Edge Cases

| Scenario | Behavior |
|:---|:---|
| `investors/` doesn't exist | Returns empty `investors: []`, no error |
| `profile.yaml` parse error | Skips that investor, adds to `warnings` |
| `portfolio.yaml` parse error | Skips that portfolio, adds to `warnings` |
| `transactions.jsonl` doesn't exist | `ledger.total_records = 0` |
| Corrupt lines in ledger | Skips corrupt lines, records in `warnings` |
| `strategies/` doesn't exist | Returns empty `strategies: []` |
| Empty workspace (brand new) | Returns all-empty + `quick_start` suggesting `init_investor_tool` |

## Testing

- `tests/test_workspace.py`: ~8 tests
  - Empty workspace → empty results
  - Single investor + portfolio → correct discovery
  - Corrupt YAML → skipped with warning
  - Ledger stats counting
  - NAV history scanning
  - Quick start generation logic
  - Staleness calculation
  - Full integration test

## Success Criteria

1. Agent calls `discover_workspace_tool()` as first tool after MCP connection
2. Response contains correct investor ID, portfolio ID, and ticker list
3. Agent uses returned IDs in subsequent tool calls (no more wrong-ID errors)
4. Zero parameters required — works on any workspace without prior knowledge
