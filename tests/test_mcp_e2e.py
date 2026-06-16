"""MCP 工具端到端测试"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock


class TestMCPEndToEnd:
    """MCP 工具端到端测试"""

    def test_portfolio_tools(self):
        """测试组合管理工具"""
        from praxis.tools.portfolio import get_portfolio, get_asset_detail

        # 测试 get_portfolio
        result = get_portfolio("example", "core")
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_asset_detail
        result = get_asset_detail("example", "core", "ETF_300")
        assert isinstance(result, dict)
        assert "success" in result

    def test_market_tools(self):
        """测试市场数据工具"""
        from praxis.tools.market import get_market_data

        # 测试 get_market_data
        result = asyncio.run(get_market_data(["ETF_300"]))
        assert isinstance(result, dict)
        assert "success" in result

    def test_engine_tools(self):
        """测试引擎工具"""
        from praxis.tools.engine import reconcile, check_constraints

        # 测试 reconcile
        result = asyncio.run(reconcile("example", "core"))
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 check_constraints
        result = check_constraints("example", "core", "buy", "ETF_300", 1000)
        assert isinstance(result, dict)
        assert "success" in result

    def test_ledger_tools(self):
        """测试交易账本工具"""
        from praxis.tools.ledger import get_ledger, add_transaction, reverse_transaction, approve_transaction

        # 测试 get_ledger
        result = get_ledger()
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 add_transaction
        result = add_transaction("buy", "ETF_300", 100, 4.0)
        assert isinstance(result, dict)
        assert "success" in result

    def test_decision_tools(self):
        """测试决策工具"""
        from praxis.tools.decision import get_decision_record, list_decisions, create_decision

        # 测试 list_decisions
        result = list_decisions()
        assert isinstance(result, dict)
        assert "success" in result

    def test_performance_tools(self):
        """测试绩效工具"""
        from praxis.tools.performance import get_performance

        # 测试 get_performance
        result = asyncio.run(get_performance("example", "core"))
        assert isinstance(result, dict)
        assert "success" in result

    def test_strategy_tools(self):
        """测试策略工具"""
        from praxis.tools.strategy import get_strategy, list_strategies

        # 测试 list_strategies
        result = list_strategies()
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_strategy
        result = get_strategy("grid_value")
        assert isinstance(result, dict)
        assert "success" in result

    def test_evolution_tools(self):
        """测试进化工具"""
        from praxis.tools.evolution import evaluate_evolution, evolve_strategy

        # 测试 evaluate_evolution
        result = evaluate_evolution("example", "core", "grid_value")
        assert isinstance(result, dict)
        assert "success" in result

    def test_benchmark_tools(self):
        """测试基准工具"""
        from praxis.tools.benchmark import get_benchmark_data, list_benchmarks

        # 测试 list_benchmarks
        result = list_benchmarks()
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_benchmark_data
        result = asyncio.run(get_benchmark_data("000300", 30))
        assert isinstance(result, dict)
        assert "success" in result

    def test_nav_tools(self):
        """测试净值工具"""
        from praxis.tools.nav import record_nav, get_nav_snapshot, get_nav_history

        # 测试 get_nav_snapshot
        result = asyncio.run(get_nav_snapshot("example", "core"))
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_nav_history
        result = get_nav_history("example", "core")
        assert isinstance(result, dict)
        assert "success" in result

    def test_ai_tracking_tools(self):
        """测试 AI 追踪工具"""
        from praxis.tools.ai_tracking import get_ai_tracking

        # 测试 get_ai_tracking
        result = get_ai_tracking()
        assert isinstance(result, dict)
        assert "success" in result

    def test_teams_tools(self):
        """测试团队工具"""
        from praxis.tools.teams import list_teams, get_team_prompt, compose_team_prompt

        # 测试 list_teams
        result = list_teams()
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_team_prompt
        result = get_team_prompt("asrg")
        assert isinstance(result, dict)
        assert "success" in result

    def test_template_tools(self):
        """测试模板工具"""
        from praxis.tools.teams import list_output_templates, get_output_template

        # 测试 list_output_templates
        result = list_output_templates()
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_output_template
        result = get_output_template("asrg_output")
        assert isinstance(result, dict)
        assert "success" in result

    def test_review_tools(self):
        """测试复盘工具"""
        from praxis.tools.review import get_review_summary, get_confidence_calibration

        # 测试 get_review_summary
        result = get_review_summary()
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_confidence_calibration
        result = get_confidence_calibration("asrg")
        assert isinstance(result, dict)
        assert "success" in result

    def test_friction_tools(self):
        """测试交易摩擦工具"""
        from praxis.tools.friction import calculate_fee, calculate_slippage, check_trading_time, get_confirm_date

        # 测试 calculate_fee
        result = calculate_fee("ETF_300", "etf", "buy", 100, 4.0)
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 calculate_slippage
        result = calculate_slippage(4.0, "buy")
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 check_trading_time
        result = check_trading_time()
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_confirm_date
        result = get_confirm_date("2026-06-06", "stock")
        assert isinstance(result, dict)
        assert "success" in result

    def test_data_quality_tools(self):
        """测试数据质量工具"""
        from praxis.tools.data_quality import check_quote_quality, clean_quote_data, get_quality_report

        # 测试 check_quote_quality
        result = check_quote_quality("ETF_300", {"close": 4.0, "volume": 1000000})
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_quality_report
        result = get_quality_report()
        assert isinstance(result, dict)
        assert "success" in result

    def test_prompt_versioning_tools(self):
        """测试 Prompt 版本工具"""
        from praxis.tools.prompt_versioning import list_prompt_versions, get_prompt_version, check_prompt_safety

        # 测试 list_prompt_versions
        result = list_prompt_versions("asrg")
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 get_prompt_version
        result = get_prompt_version("asrg")
        assert isinstance(result, dict)
        assert "success" in result

        # 测试 check_prompt_safety
        result = check_prompt_safety("测试文本")
        assert isinstance(result, dict)
        assert "success" in result

    def test_backtest_tools(self):
        """测试回测工具"""
        from praxis.tools.backtest import run_backtest

        # 测试 run_backtest
        result = asyncio.run(run_backtest("grid_value", "example", "core"))
        assert isinstance(result, dict)
        assert "success" in result

    def test_version_compare_tools(self):
        """测试版本对比工具"""
        from praxis.tools.version_compare import compare_versions

        # 测试 compare_versions
        result = asyncio.run(compare_versions("v1.0", "v1.1"))
        assert isinstance(result, dict)
        assert "success" in result

    def test_grayscale_tools(self):
        """测试灰度发布工具"""
        from praxis.tools.grayscale import prepare_grayscale

        # 测试 prepare_grayscale
        result = prepare_grayscale("grid_value", "测试灰度", "low")
        assert isinstance(result, dict)
        assert "success" in result

    def test_state_tools(self):
        """测试状态工具"""
        from praxis.tools.state import get_state

        # 测试 get_state
        result = asyncio.run(get_state("example", "core"))
        assert isinstance(result, dict)
        assert "success" in result
