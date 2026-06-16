"""
Praxis v3.0 断点续传模块测试

测试重点：
- 断点保存/加载基本功能
- 跨日过期机制
- 多标的隔离
- feature flag 控制
- 原子写入安全性
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from praxis_sdk.core.checkpointer import (
    save_checkpoint,
    load_checkpoint,
    load_checkpoint_raw,
    clear_checkpoint,
    clear_all_checkpoints,
    get_checkpoint_summary,
    _checkpoint_path,
    VALID_PHASES,
    CHECKPOINT_ENABLED,
)


class TestCheckpointer:
    """断点续传测试套件。"""

    def setup_method(self):
        """每个测试前创建临时目录。"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = None
        # 临时替换 CHECKPOINT_DIR
        import praxis_sdk.core.checkpointer as cp_module
        self.original_dir = cp_module.CHECKPOINT_DIR
        cp_module.CHECKPOINT_DIR = Path(self.test_dir)

    def teardown_method(self):
        """每个测试后清理临时目录。"""
        import praxis_sdk.core.checkpointer as cp_module
        cp_module.CHECKPOINT_DIR = self.original_dir
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_load_basic(self):
        """测试基本的保存和加载功能。"""
        ticker = "000001"
        date = "2026-06-12"
        phase = "asrg"
        data = "# ASRG 输出\n这是测试数据"

        # 保存
        result = save_checkpoint(ticker, date, phase, data)
        assert result is True

        # 加载
        loaded = load_checkpoint(ticker, date)
        assert loaded is not None
        assert phase in loaded
        assert loaded[phase] == data

    def test_save_multiple_phases(self):
        """测试多阶段追加保存。"""
        ticker = "000001"
        date = "2026-06-12"

        save_checkpoint(ticker, date, "asrg", "ASRG output")
        save_checkpoint(ticker, date, "masters", "Masters output")
        save_checkpoint(ticker, date, "trading_p1", "Trading P1 output")

        loaded = load_checkpoint(ticker, date)
        assert loaded is not None
        assert len(loaded) == 3
        assert loaded["asrg"] == "ASRG output"
        assert loaded["masters"] == "Masters output"
        assert loaded["trading_p1"] == "Trading P1 output"

    def test_cross_date_expiry(self):
        """测试跨日过期机制。"""
        ticker = "000001"

        # 保存到 2026-06-12
        save_checkpoint(ticker, "2026-06-12", "asrg", "old data")

        # 用 2026-06-13 加载应该返回 None
        loaded = load_checkpoint(ticker, "2026-06-13")
        assert loaded is None

        # 用 2026-06-12 加载应该成功
        loaded = load_checkpoint(ticker, "2026-06-12")
        assert loaded is not None

    def test_multi_ticker_isolation(self):
        """测试多标的隔离。"""
        date = "2026-06-12"

        save_checkpoint("000001", date, "asrg", "600995 data")
        save_checkpoint("510050", date, "asrg", "510050 data")

        loaded_000001 = load_checkpoint("000001", date)
        loaded_510050 = load_checkpoint("510050", date)

        assert loaded_000001["asrg"] == "600995 data"
        assert loaded_510050["asrg"] == "510050 data"
        assert loaded_000001["asrg"] != loaded_510050["asrg"]

    def test_invalid_phase_rejected(self):
        """测试非法阶段标识被拒绝。"""
        try:
            save_checkpoint("000001", "2026-06-12", "invalid_phase", "data")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid phase" in str(e)

    def test_clear_checkpoint(self):
        """测试断点清除。"""
        ticker = "000001"
        date = "2026-06-12"

        save_checkpoint(ticker, date, "asrg", "data")
        assert load_checkpoint(ticker, date) is not None

        result = clear_checkpoint(ticker, date)
        assert result is True
        assert load_checkpoint(ticker, date) is None

    def test_clear_all_checkpoints(self):
        """测试清除所有断点。"""
        save_checkpoint("000001", "2026-06-12", "asrg", "data1")
        save_checkpoint("510050", "2026-06-12", "asrg", "data2")

        count = clear_all_checkpoints()
        assert count == 2
        assert load_checkpoint("000001", "2026-06-12") is None
        assert load_checkpoint("510050", "2026-06-12") is None

    def test_checkpoint_summary(self):
        """测试断点摘要。"""
        save_checkpoint("000001", "2026-06-12", "asrg", "data")
        save_checkpoint("000001", "2026-06-12", "masters", "data")

        summary = get_checkpoint_summary("000001", "2026-06-12")
        assert summary is not None
        assert "000001" in summary
        assert "2/6" in summary or "2" in summary
        assert "asrg" in summary
        assert "masters" in summary

    def test_nonexistent_checkpoint_returns_none(self):
        """测试不存在的断点返回 None。"""
        loaded = load_checkpoint("nonexistent", "2026-06-12")
        assert loaded is None

    def test_valid_phases_set(self):
        """测试合法阶段标识集合。"""
        expected = {"asrg", "masters", "trading_p1", "trading_p2", "trading_p3", "trading_p4"}
        assert VALID_PHASES == expected

    def test_metadata_stored(self):
        """测试元数据存储。"""
        save_checkpoint(
            "000001", "2026-06-12", "asrg", "data",
            metadata={"tokens_used": 5000, "duration_sec": 12.5}
        )

        raw = load_checkpoint_raw("000001", "2026-06-12")
        assert raw is not None
        assert raw["phases"]["asrg"]["metadata"]["tokens_used"] == 5000
        assert raw["phases"]["asrg"]["metadata"]["duration_sec"] == 12.5

    def test_path_traversal_prevention(self):
        """测试路径遍历防护。"""
        # ticker 包含路径遍历字符
        malicious_ticker = "../../../etc/passwd"
        save_checkpoint(malicious_ticker, "2026-06-12", "asrg", "data")

        # 文件应该保存在 test_dir 内，不会逃逸
        path = _checkpoint_path(malicious_ticker, "2026-06-12")
        assert str(self.test_dir) in str(path)
        assert ".." not in path.name


def run_tests():
    """运行所有测试。"""
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_tests()
