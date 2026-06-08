# Design Spec: Praxis MCP Server Lazy Import 启动优化

> **Date**: 2026-06-08
> **Status**: Approved for implementation
> **Scope**: `praxis/mcp_server.py` 启动性能优化

---

## Problem Statement

Praxis MCP Server 启动耗时 10-15 秒，用户需要等待甚至重启才能使用。根因：

1. **29 个 eager import**：所有 `praxis.tools.*` 和 `praxis.core.*` 在模块加载时全部导入
2. **传递依赖链**：每个 tools 模块又导入 engine 层（创建 httpx 客户端、读取 JSONL 文件、初始化缓存）
3. **63 个工具 schema 生成**：`@mcp.tool()` 需要为每个工具生成 JSON Schema

启动时加载了大量不需要立即使用的业务逻辑。

## Solution

将所有顶部 import 改为工具函数内部 lazy import。启动时只注册 MCP 工具的 schema（纯元数据），不加载任何业务代码。

## Implementation

### Files to Change

| File | Action | Lines Changed |
|:---|:---|:---|
| `praxis/mcp_server.py` | **Modify** | 删除 ~32 行 import，每个工具函数内添加 1 行 import |

### Before (current)

```python
"""PRAXIS MCP Server 入口"""
from __future__ import annotations

import asyncio
import os
import time
from mcp.server.fastmcp import FastMCP

from praxis.tools.portfolio import get_portfolio, get_asset_detail
from praxis.tools.market import get_market_data
from praxis.tools.engine import reconcile, check_constraints
from praxis.tools.ledger import get_ledger, add_transaction, approve_transaction, reverse_transaction, delete_transaction, purge_ledger, reject_transaction, list_pending_transactions
from praxis.tools.state import get_state
from praxis.tools.decision import get_decision_record, list_decisions, create_decision
from praxis.tools.performance import get_performance
from praxis.tools.strategy import get_strategy, list_strategies, update_portfolio
from praxis.tools.evolution import evaluate_evolution, evolve_strategy
from praxis.tools.benchmark import get_benchmark_data, list_benchmarks
from praxis.tools.nav import record_nav, get_nav_snapshot, get_nav_history
from praxis.tools.ai_tracking import get_ai_tracking
from praxis.tools.teams import list_teams, get_team_prompt, compose_team_prompt, list_output_templates, get_output_template, update_output_template, approve_output_template_update, create_output_template
from praxis.tools.review import fill_reviews, get_review_summary, get_confidence_calibration
from praxis.tools.backtest import run_backtest, compare_strategy_versions
from praxis.tools.version_compare import compare_versions
from praxis.tools.grayscale import prepare_grayscale, approve_grayscale
from praxis.tools.friction import calculate_fee, calculate_slippage, check_trading_time, get_confirm_date
from praxis.tools.data_quality import check_quote_quality, clean_quote_data, get_quality_report
from praxis.tools.prompt_versioning import list_prompt_versions, get_prompt_version, create_prompt_version, rollback_prompt, check_prompt_safety, get_version_diff
from praxis.tools.investor import create_investor, create_portfolio, init_investor
from praxis.tools.summary import get_portfolio_summary
from praxis.tools.workspace import discover_workspace
from praxis.core.logger import get_logger, init_logger
```

### After (lazy)

```python
"""PRAXIS MCP Server 入口"""
from __future__ import annotations

import os
from mcp.server.fastmcp import FastMCP

# 创建 MCP Server
mcp = FastMCP("PRAXIS", json_response=True)

# 获取工作目录
WORKSPACE = os.environ.get("PRAXIS_WORKSPACE", ".")

# 延迟初始化 logger（首次写操作时触发）
_logger_initialized = False

def _ensure_logger():
    global _logger_initialized
    if not _logger_initialized:
        from praxis.core.logger import init_logger
        init_logger(log_dir=os.path.join(WORKSPACE, "data", "logs"))
        _logger_initialized = True

async def _log_tool_call(tool_name: str, func, *args, **kwargs):
    """记录工具调用的辅助函数"""
    _ensure_logger()
    from praxis.core.logger import get_logger
    import time
    logger = get_logger()
    start_time = time.time()
    try:
        result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.tool_call(
            tool_name=tool_name, parameters=kwargs,
            success=result.get("success", True),
            duration_ms=duration_ms, error=result.get("error"),
        )
        return result
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.tool_call(
            tool_name=tool_name, parameters=kwargs,
            success=False, duration_ms=duration_ms, error=str(e),
        )
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_portfolio_tool(investor: str, portfolio: str) -> dict:
    """读取投资组合配置"""
    from praxis.tools.portfolio import get_portfolio
    return get_portfolio(investor=investor, portfolio=portfolio, workspace=WORKSPACE)


@mcp.tool()
async def get_market_data_tool(tickers: list[str]) -> dict:
    """获取实时行情数据"""
    from praxis.tools.market import get_market_data
    return await get_market_data(tickers)

# ... 所有 63 个工具都按此模式改造
```

### Tool-by-Tool Import Mapping

Each tool function gets exactly one `from praxis.tools.X import Y` line inside its body:

| Tool Function | Import (lazy) |
|:---|:---|
| `get_portfolio_tool` | `from praxis.tools.portfolio import get_portfolio` |
| `get_asset_detail_tool` | `from praxis.tools.portfolio import get_asset_detail` |
| `get_market_data_tool` | `from praxis.tools.market import get_market_data` |
| `reconcile_tool` | `from praxis.tools.engine import reconcile` |
| `check_constraints_tool` | `from praxis.tools.engine import check_constraints` |
| `get_state_tool` | `from praxis.tools.state import get_state` |
| `get_ledger_tool` | `from praxis.tools.ledger import get_ledger` |
| `add_transaction_tool` | `from praxis.tools.ledger import add_transaction` |
| `approve_transaction_tool` | `from praxis.tools.ledger import approve_transaction` |
| `reverse_transaction_tool` | `from praxis.tools.ledger import reverse_transaction` |
| `delete_transaction_tool` | `from praxis.tools.ledger import delete_transaction` |
| `purge_ledger_tool` | `from praxis.tools.ledger import purge_ledger` |
| `reject_transaction_tool` | `from praxis.tools.ledger import reject_transaction` |
| `list_pending_transactions_tool` | `from praxis.tools.ledger import list_pending_transactions` |
| `get_performance_tool` | `from praxis.tools.performance import get_performance` |
| `get_strategy_tool` | `from praxis.tools.strategy import get_strategy` |
| `list_strategies_tool` | `from praxis.tools.strategy import list_strategies` |
| `update_portfolio_tool` | `from praxis.tools.strategy import update_portfolio` |
| `evaluate_evolution_tool` | `from praxis.tools.evolution import evaluate_evolution` |
| `evolve_strategy_tool` | `from praxis.tools.evolution import evolve_strategy` |
| `get_benchmark_data_tool` | `from praxis.tools.benchmark import get_benchmark_data` |
| `list_benchmarks_tool` | `from praxis.tools.benchmark import list_benchmarks` |
| `record_nav_tool` | `from praxis.tools.nav import record_nav` |
| `get_nav_snapshot_tool` | `from praxis.tools.nav import get_nav_snapshot` |
| `get_nav_history_tool` | `from praxis.tools.nav import get_nav_history` |
| `get_ai_tracking_tool` | `from praxis.tools.ai_tracking import get_ai_tracking` |
| `list_teams_tool` | `from praxis.tools.teams import list_teams` |
| `get_team_prompt_tool` | `from praxis.tools.teams import get_team_prompt` |
| `compose_team_prompt_tool` | `from praxis.tools.teams import compose_team_prompt` |
| `list_output_templates_tool` | `from praxis.tools.teams import list_output_templates` |
| `get_output_template_tool` | `from praxis.tools.teams import get_output_template` |
| `update_output_template_tool` | `from praxis.tools.teams import update_output_template` |
| `approve_output_template_update_tool` | `from praxis.tools.teams import approve_output_template_update` |
| `create_output_template_tool` | `from praxis.tools.teams import create_output_template` |
| `fill_reviews_tool` | `from praxis.tools.review import fill_reviews` |
| `get_review_summary_tool` | `from praxis.tools.review import get_review_summary` |
| `get_confidence_calibration_tool` | `from praxis.tools.review import get_confidence_calibration` |
| `run_backtest_tool` | `from praxis.tools.backtest import run_backtest` |
| `compare_strategy_versions_tool` | `from praxis.tools.backtest import compare_strategy_versions` |
| `compare_versions_tool` | `from praxis.tools.version_compare import compare_versions` |
| `prepare_grayscale_tool` | `from praxis.tools.grayscale import prepare_grayscale` |
| `approve_grayscale_tool` | `from praxis.tools.grayscale import approve_grayscale` |
| `calculate_fee_tool` | `from praxis.tools.friction import calculate_fee` |
| `calculate_slippage_tool` | `from praxis.tools.friction import calculate_slippage` |
| `check_trading_time_tool` | `from praxis.tools.friction import check_trading_time` |
| `get_confirm_date_tool` | `from praxis.tools.friction import get_confirm_date` |
| `check_quote_quality_tool` | `from praxis.tools.data_quality import check_quote_quality` |
| `clean_quote_data_tool` | `from praxis.tools.data_quality import clean_quote_data` |
| `get_quality_report_tool` | `from praxis.tools.data_quality import get_quality_report` |
| `list_prompt_versions_tool` | `from praxis.tools.prompt_versioning import list_prompt_versions` |
| `get_prompt_version_tool` | `from praxis.tools.prompt_versioning import get_prompt_version` |
| `create_prompt_version_tool` | `from praxis.tools.prompt_versioning import create_prompt_version` |
| `rollback_prompt_tool` | `from praxis.tools.prompt_versioning import rollback_prompt` |
| `check_prompt_safety_tool` | `from praxis.tools.prompt_versioning import check_prompt_safety` |
| `get_version_diff_tool` | `from praxis.tools.prompt_versioning import get_version_diff` |
| `create_investor_tool` | `from praxis.tools.investor import create_investor` |
| `create_portfolio_tool` | `from praxis.tools.investor import create_portfolio` |
| `init_investor_tool` | `from praxis.tools.investor import init_investor` |
| `get_portfolio_summary_tool` | `from praxis.tools.summary import get_portfolio_summary` |
| `discover_workspace_tool` | `from praxis.tools.workspace import discover_workspace` |
| `get_decision_record_tool` | `from praxis.tools.decision import get_decision_record` |
| `list_decisions_tool` | `from praxis.tools.decision import list_decisions` |
| `create_decision_tool` | `from praxis.tools.decision import create_decision` |
| `get_review_summary_tool` | `from praxis.tools.review import get_review_summary` |

## Edge Cases

| Scenario | Behavior |
|:---|:---|
| First call to any tool | ~100ms extra for import, then cached by Python |
| Import error in a tool | Only that tool fails, other tools unaffected |
| `asyncio` dependency | Re-add `import asyncio` at top if `_log_tool_call` needs it |
| Circular imports | Tools are leaf modules, no circular dependency risk |

## Success Criteria

1. MCP server startup time < 3 seconds (currently 10-15s)
2. All 63 tools still functional after migration
3. No regression in tool behavior
4. First-call latency < 200ms per tool
