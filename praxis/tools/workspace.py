"""MCP Tool — Workspace Discovery

Zero-parameter tool that scans the workspace and returns a complete map:
investors, portfolios, ledger stats, strategies, data freshness, and
recommended next calls. Designed to be the first tool an agent calls
after connecting to Praxis MCP.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
    investors: list[dict] = []
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
        investor: dict = {
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
        return {
            "total_records": 0,
            "confirmed": 0,
            "pending": 0,
            "unique_tickers": [],
            "latest_transaction": None,
            "tags_seen": [],
        }

    total = confirmed = pending = 0
    tickers: set[str] = set()
    tags_seen: set[str] = set()
    latest_date = None

    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                total += 1
                status = rec.get("status", "confirmed")
                if status == "confirmed":
                    confirmed += 1
                elif status == "pending":
                    pending += 1
                t = rec.get("ticker", "")
                if t:
                    tickers.add(t)
                for tag in rec.get("tags", []):
                    tags_seen.add(tag)
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
        "tags_seen": sorted(tags_seen),
    }


def _scan_nav(ws: Path) -> dict:
    """Scan nav history."""
    nav_dir = ws / "data" / "nav"
    if not nav_dir.exists():
        return {"record_count": 0, "latest_date": None}

    count = 0
    latest = None
    # Support both default.jsonl and any .jsonl in the nav dir
    for nav_file in sorted(nav_dir.glob("*.jsonl")):
        with open(nav_file, "r", encoding="utf-8") as f:
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
    calls: list[str] = []

    if investors and investors[0].get("portfolios"):
        inv = investors[0]["id"]
        port = investors[0]["portfolios"][0]["id"]
        calls.append(f"get_portfolio_summary_tool(investor='{inv}', portfolio='{port}')")

        tags_seen = ledger.get("tags_seen", [])
        has_migration = any(t in ("opening", "migration") for t in tags_seen)
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


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def discover_workspace(workspace: str = ".") -> dict:
    """Discover workspace state — zero parameters required.

    Scans the workspace directory and returns a complete map of investors,
    portfolios, ledger stats, strategies, data freshness, and recommended
    next tool calls.
    """
    try:
        ws = Path(workspace).resolve()
        warnings: list[str] = []

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
