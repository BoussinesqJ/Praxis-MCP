"""多模块协作测试"""
import pytest
import asyncio


class TestMultiModuleCollaboration:
    """多模块协作测试"""

    def test_portfolio_to_market_flow(self):
        """测试组合到市场数据流程"""
        from praxis.tools.portfolio import get_portfolio
        from praxis.tools.market import get_market_data

        # 1. 获取组合
        portfolio = get_portfolio("example", "demo")
        assert portfolio["success"] is True

        # 2. 获取市场数据
        market = asyncio.run(get_market_data(["ETF_300"]))
        assert market["success"] is True

    def test_portfolio_to_state_flow(self):
        """测试组合到状态流程"""
        from praxis.tools.portfolio import get_portfolio
        from praxis.tools.state import get_state

        # 1. 获取组合
        portfolio = get_portfolio("example", "demo")
        assert portfolio["success"] is True

        # 2. 获取状态
        state = asyncio.run(get_state("example", "demo"))
        assert state["success"] is True

    def test_decision_to_ledger_flow(self):
        """测试决策到账本流程"""
        from praxis.tools.decision import create_decision, list_decisions
        from praxis.tools.ledger import add_transaction, get_ledger

        # 1. 创建决策
        decision = create_decision("buy", "测试决策", 0.8, "ETF_300")
        assert decision["success"] is True

        # 2. 添加交易
        tx = add_transaction("ETF_300", "buy", 100, 4.0)
        assert tx["success"] is True

        # 3. 获取账本
        ledger = get_ledger()
        assert ledger["success"] is True

    def test_strategy_to_evolution_flow(self):
        """测试策略到进化流程"""
        from praxis.tools.strategy import get_strategy
        from praxis.tools.evolution import evaluate_evolution

        # 1. 获取策略
        strategy = get_strategy("grid_value")
        assert strategy["success"] is True

        # 2. 评估进化
        evolution = evaluate_evolution("grid_value", "example", "demo")
        assert evolution["success"] is True

    def test_performance_to_benchmark_flow(self):
        """测试绩效到基准流程"""
        from praxis.tools.performance import get_performance
        from praxis.tools.benchmark import get_benchmark_data

        # 1. 获取绩效
        performance = asyncio.run(get_performance("example", "demo"))
        assert performance["success"] is True

        # 2. 获取基准数据（可能因网络问题失败）
        benchmark = asyncio.run(get_benchmark_data("000300", 30))
        # 基准数据可能因网络问题失败，所以不强制要求成功
        assert isinstance(benchmark, dict)

    def test_teams_to_template_flow(self):
        """测试团队到模板流程"""
        from praxis.tools.teams import list_teams, get_team_prompt, list_output_templates

        # 1. 列出团队
        teams = list_teams()
        assert teams["success"] is True

        # 2. 获取团队 Prompt
        prompt = get_team_prompt("asrg")
        assert prompt["success"] is True

        # 3. 列出输出模板
        templates = list_output_templates()
        assert templates["success"] is True

    def test_review_to_calibration_flow(self):
        """测试复盘到校准流程"""
        from praxis.tools.review import get_review_summary, get_confidence_calibration

        # 1. 获取复盘汇总
        summary = get_review_summary()
        assert summary["success"] is True

        # 2. 获取置信度校准
        calibration = get_confidence_calibration("asrg")
        assert calibration["success"] is True

    def test_friction_to_decision_flow(self):
        """测试交易摩擦到决策流程"""
        from praxis.tools.friction import calculate_fee, calculate_slippage
        from praxis.tools.decision import create_decision

        # 1. 计算费用
        fee = calculate_fee("ETF_300", "etf", "buy", 100, 4.0)
        assert fee["success"] is True

        # 2. 计算滑点
        slippage = calculate_slippage(4.0, "buy")
        assert slippage["success"] is True

        # 3. 创建决策
        decision = create_decision("buy", "测试决策", 0.8, "ETF_300")
        assert decision["success"] is True

    def test_data_quality_to_market_flow(self):
        """测试数据质量到市场流程"""
        from praxis.tools.data_quality import check_quote_quality, get_quality_report
        from praxis.tools.market import get_market_data

        # 1. 检查行情质量
        quality = check_quote_quality("ETF_300", {"close": 4.0, "volume": 1000000})
        assert quality["success"] is True

        # 2. 获取质量报告
        report = get_quality_report()
        assert report["success"] is True

        # 3. 获取市场数据
        market = asyncio.run(get_market_data(["ETF_300"]))
        assert market["success"] is True

    def test_prompt_versioning_to_safety_flow(self):
        """测试 Prompt 版本到安全流程"""
        from praxis.tools.prompt_versioning import list_prompt_versions, check_prompt_safety

        # 1. 列出版本
        versions = list_prompt_versions("asrg")
        assert versions["success"] is True

        # 2. 检查安全性
        safety = check_prompt_safety("测试文本")
        assert safety["success"] is True
