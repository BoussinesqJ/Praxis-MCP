"""真实数据场景测试"""
import pytest
import asyncio


class TestRealDataScenarios:
    """真实数据场景测试"""

    def test_real_portfolio_scenario(self):
        """测试真实组合场景"""
        from praxis.tools.portfolio import get_portfolio
        from praxis.tools.state import get_state
        from praxis.tools.performance import get_performance

        # 1. 获取真实组合
        portfolio = get_portfolio("example", "demo")
        assert portfolio["success"] is True

        # 2. 获取状态
        state = asyncio.run(get_state("example", "demo"))
        assert state["success"] is True

        # 3. 获取绩效
        performance = asyncio.run(get_performance("example", "demo"))
        assert performance["success"] is True

    def test_real_decision_scenario(self):
        """测试真实决策场景"""
        from praxis.tools.decision import create_decision, list_decisions
        from praxis.tools.ledger import add_transaction, get_ledger

        # 1. 创建决策
        decision = create_decision("buy", "真实决策测试", 0.7, "ETF_300")
        assert decision["success"] is True

        # 2. 添加交易
        tx = add_transaction("ETF_300", "buy", 100, 4.0)
        assert tx["success"] is True

        # 3. 获取账本
        ledger = get_ledger()
        assert ledger["success"] is True

    def test_real_strategy_scenario(self):
        """测试真实策略场景"""
        from praxis.tools.strategy import get_strategy, list_strategies
        from praxis.tools.evolution import evaluate_evolution

        # 1. 列出策略
        strategies = list_strategies()
        assert strategies["success"] is True

        # 2. 获取策略
        strategy = get_strategy("grid_value")
        assert strategy["success"] is True

        # 3. 评估进化
        evolution = evaluate_evolution("grid_value", "example", "demo")
        assert evolution["success"] is True

    def test_real_market_scenario(self):
        """测试真实市场场景"""
        from praxis.tools.market import get_market_data
        from praxis.tools.data_quality import check_quote_quality

        # 1. 获取市场数据
        market = asyncio.run(get_market_data(["ETF_300"]))
        assert market["success"] is True

        # 2. 检查数据质量
        quality = check_quote_quality("ETF_300", {"close": 4.0, "volume": 1000000})
        assert quality["success"] is True

    def test_real_teams_scenario(self):
        """测试真实团队场景"""
        from praxis.tools.teams import list_teams, get_team_prompt, compose_team_prompt

        # 1. 列出团队
        teams = list_teams()
        assert teams["success"] is True

        # 2. 获取团队 Prompt
        prompt = get_team_prompt("asrg")
        assert prompt["success"] is True

        # 3. 组合团队 Prompt
        composed = compose_team_prompt("asrg", "grid_value", "example")
        assert composed["success"] is True

    def test_real_review_scenario(self):
        """测试真实复盘场景"""
        from praxis.tools.review import get_review_summary, get_confidence_calibration

        # 1. 获取复盘汇总
        summary = get_review_summary()
        assert summary["success"] is True

        # 2. 获取置信度校准
        calibration = get_confidence_calibration("asrg")
        assert calibration["success"] is True

    def test_real_friction_scenario(self):
        """测试真实交易摩擦场景"""
        from praxis.tools.friction import calculate_fee, calculate_slippage, check_trading_time

        # 1. 计算费用
        fee = calculate_fee("ETF_300", "etf", "buy", 100, 4.0)
        assert fee["success"] is True

        # 2. 计算滑点
        slippage = calculate_slippage(4.0, "buy")
        assert slippage["success"] is True

        # 3. 检查交易时间
        trading_time = check_trading_time()
        assert trading_time["success"] is True

    def test_real_prompt_scenario(self):
        """测试真实 Prompt 场景"""
        from praxis.tools.prompt_versioning import list_prompt_versions, check_prompt_safety

        # 1. 列出版本
        versions = list_prompt_versions("asrg")
        assert versions["success"] is True

        # 2. 检查安全性
        safety = check_prompt_safety("测试文本")
        assert safety["success"] is True

    def test_real_backtest_scenario(self):
        """测试真实回测场景"""
        from praxis.tools.backtest import run_backtest

        # 1. 运行回测
        backtest = asyncio.run(run_backtest("grid_value", "example", "demo"))
        assert backtest["success"] is True

    def test_real_grayscale_scenario(self):
        """测试真实灰度发布场景"""
        from praxis.tools.grayscale import prepare_grayscale

        # 1. 准备灰度
        grayscale = prepare_grayscale("grid_value", "测试灰度", "low")
        assert grayscale["success"] is True
