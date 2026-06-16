"""测试配置"""
from pathlib import Path

# 测试数据目录
TEST_DATA_DIR = Path(__file__).parent / "data"
TEST_DATA_DIR.mkdir(exist_ok=True)

# 测试用的投资者ID
TEST_INVESTOR = "example"
TEST_PORTFOLIO = "demo"

# 测试用的工作目录（使用真实的工作目录）
TEST_WORKSPACE = Path(__file__).parent.parent
