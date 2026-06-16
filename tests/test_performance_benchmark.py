"""性能基准测试"""
import pytest
import asyncio
import time


class TestPerformanceBenchmark:
    """性能基准测试"""

    def test_portfolio_performance(self):
        """测试组合查询性能"""
        from praxis.tools.portfolio import get_portfolio

        start_time = time.time()
        for _ in range(10):
            get_portfolio("example", "demo")
        end_time = time.time()

        # 10 次查询应该在 1 秒内完成
        assert end_time - start_time < 1.0

    def test_market_data_performance(self):
        """测试市场数据性能"""
        from praxis.tools.market import get_market_data

        start_time = time.time()
        for _ in range(10):
            asyncio.run(get_market_data(["ETF_300"]))
        end_time = time.time()

        # 10 次查询应该在 20 秒内完成（网络请求）
        assert end_time - start_time < 20.0

    def test_state_performance(self):
        """测试状态查询性能"""
        from praxis.tools.state import get_state

        start_time = time.time()
        for _ in range(10):
            asyncio.run(get_state("example", "demo"))
        end_time = time.time()

        # 10 次查询应该在 20 秒内完成
        assert end_time - start_time < 20.0

    def test_ledger_performance(self):
        """测试账本查询性能"""
        from praxis.tools.ledger import get_ledger

        start_time = time.time()
        for _ in range(10):
            get_ledger()
        end_time = time.time()

        # 10 次查询应该在 1 秒内完成
        assert end_time - start_time < 1.0

    def test_decision_performance(self):
        """测试决策查询性能"""
        from praxis.tools.decision import list_decisions

        start_time = time.time()
        for _ in range(10):
            list_decisions()
        end_time = time.time()

        # 10 次查询应该在 1 秒内完成
        assert end_time - start_time < 1.0

    def test_performance_performance(self):
        """测试绩效查询性能"""
        from praxis.tools.performance import get_performance

        start_time = time.time()
        for _ in range(10):
            asyncio.run(get_performance("example", "demo"))
        end_time = time.time()

        # 10 次查询应该在 20 秒内完成
        assert end_time - start_time < 20.0

    def test_strategy_performance(self):
        """测试策略查询性能"""
        from praxis.tools.strategy import list_strategies

        start_time = time.time()
        for _ in range(10):
            list_strategies()
        end_time = time.time()

        # 10 次查询应该在 1 秒内完成
        assert end_time - start_time < 1.0

    def test_teams_performance(self):
        """测试团队查询性能"""
        from praxis.tools.teams import list_teams

        start_time = time.time()
        for _ in range(10):
            list_teams()
        end_time = time.time()

        # 10 次查询应该在 1 秒内完成
        assert end_time - start_time < 1.0

    def test_review_performance(self):
        """测试复盘查询性能"""
        from praxis.tools.review import get_review_summary

        start_time = time.time()
        for _ in range(10):
            get_review_summary()
        end_time = time.time()

        # 10 次查询应该在 15 秒内完成
        assert end_time - start_time < 15.0

    def test_friction_performance(self):
        """测试交易摩擦计算性能"""
        from praxis.tools.friction import calculate_fee

        start_time = time.time()
        for _ in range(10):
            calculate_fee("ETF_300", "etf", "buy", 100, 4.0)
        end_time = time.time()

        # 10 次计算应该在 0.5 秒内完成
        assert end_time - start_time < 0.5


class TestPerformanceBenchmarkIntegration:
    """性能基准集成测试"""

    def test_concurrent_queries(self):
        """测试并发查询性能"""
        from praxis.tools.portfolio import get_portfolio

        async def concurrent_queries():
            tasks = [
                asyncio.create_task(asyncio.to_thread(get_portfolio, "example", "demo")),
                asyncio.create_task(asyncio.to_thread(get_portfolio, "example", "demo")),
                asyncio.create_task(asyncio.to_thread(get_portfolio, "example", "demo")),
            ]
            results = await asyncio.gather(*tasks)
            return results

        start_time = time.time()
        results = asyncio.run(concurrent_queries())
        end_time = time.time()

        # 并发查询应该在 3 秒内完成
        assert end_time - start_time < 3.0
        assert len(results) == 3
