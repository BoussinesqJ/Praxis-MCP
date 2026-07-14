"""tests for core/validation.py — validate_id / validate_ticker 等 4 个函数."""

from __future__ import annotations

import pytest

from praxis.core.validation import (
    validate_id,
    validate_ticker,
    is_valid_tx_id,
    is_valid_decision_id,
)


# ── 场景1：validate_id 正常通过 ────────────────────────────────────


class TestValidateIdSuccess:
    """validate_id 正常通过场景。"""

    def test_tx_id_valid(self):
        """标准交易 ID 通过。"""
        result = validate_id("tx-20250101-001", "tx")
        assert result == "tx-20250101-001"

    def test_dec_id_valid(self):
        """标准决策 ID 通过。"""
        result = validate_id("dec-20250101-005", "dec")
        assert result == "dec-20250101-005"

    def test_inv_id_valid(self):
        """投资者 ID 通过。"""
        result = validate_id("inv-alice", "inv")
        assert result == "inv-alice"

    def test_port_id_valid(self):
        """组合 ID 通过。"""
        result = validate_id("port-main", "port")
        assert result == "port-main"

    def test_strat_id_valid(self):
        """策略 ID 通过。"""
        result = validate_id("strat-grid_value", "strat")
        assert result == "strat-grid_value"


# ── 场景2：validate_id 前缀不匹配 ────────────────────────────────


class TestValidateIdPrefixMismatch:
    """validate_id 前缀不匹配抛出 ValueError。"""

    def test_wrong_prefix_raises(self):
        """错误前缀抛出 ValueError 包含 'tx-'。"""
        with pytest.raises(ValueError) as exc_info:
            validate_id("bad-id", "tx")
        assert "tx-" in str(exc_info.value)

    def test_no_prefix_raises(self):
        """没有连字符的 ID 也报错。"""
        with pytest.raises(ValueError) as exc_info:
            validate_id("badid", "tx")
        assert "tx-" in str(exc_info.value)

    def test_wrong_prefix_dec_raises(self):
        """期望 'dec' 但传入 'tx-' 开头的也报错。"""
        with pytest.raises(ValueError) as exc_info:
            validate_id("tx-20250101-001", "dec")
        assert "dec-" in str(exc_info.value)


# ── 场景3：validate_id 空/类型/长度 ────────────────────────────────


class TestValidateIdEdgeCases:
    """validate_id 边界条件：空、类型、长度。"""

    def test_empty_string_raises(self):
        """空字符串 → ValueError('ID 不能为空')。"""
        with pytest.raises(ValueError, match="ID 不能为空"):
            validate_id("", "tx")

    def test_non_string_raises(self):
        """int 类型 → ValueError('必须是字符串')。"""
        with pytest.raises(ValueError) as exc_info:
            validate_id(123, "tx")  # type: ignore[arg-type]
        assert "必须是字符串" in str(exc_info.value)

    def test_too_short_raises(self):
        """长度 <3 → ValueError('长度不足')。"""
        with pytest.raises(ValueError) as exc_info:
            validate_id("tx", "tx")
        assert "长度不足" in str(exc_info.value)

    def test_too_long_raises(self):
        """长度 >128 → ValueError('长度超限')。"""
        long_id = "tx-" + "a" * 130
        with pytest.raises(ValueError) as exc_info:
            validate_id(long_id, "tx")
        assert "长度超限" in str(exc_info.value)

    def test_exactly_three_chars(self):
        """长度 == 3 通过（最小合法长度）。"""
        result = validate_id("tx-", "tx")  # "tx-" is 3 chars
        assert result == "tx-"


# ── 场景4：validate_id 非法字符 ────────────────────────────────────


class TestValidateIdInvalidChars:
    """validate_id 非法字符检查。"""

    def test_space_raises(self):
        """含空格抛出 ValueError。"""
        with pytest.raises(ValueError) as exc_info:
            validate_id("tx-abc def", "tx")
        assert "非法字符" in str(exc_info.value)

    def test_path_separator_raises(self):
        """含路径分隔符 '/' 抛出 ValueError。"""
        with pytest.raises(ValueError) as exc_info:
            validate_id("tx-abc/def", "tx")
        assert "非法字符" in str(exc_info.value)

    def test_backslash_raises(self):
        """含反斜杠抛出 ValueError。"""
        with pytest.raises(ValueError) as exc_info:
            validate_id("tx-abc\\def", "tx")
        assert "非法字符" in str(exc_info.value)

    def test_angle_brackets_raises(self):
        """含尖括号抛出 ValueError。"""
        with pytest.raises(ValueError):
            validate_id("tx-<abc>", "tx")


# ── 场景5：validate_ticker 正常+格式化 ─────────────────────────────


class TestValidateTickerSuccess:
    """validate_ticker 正常通过并返回格式化结果。"""

    def test_a_stock_six_digits(self):
        """000001 → '000001'（保持原样，upper无影响）。"""
        assert validate_ticker("000001") == "000001"

    def test_a_stock_600519(self):
        assert validate_ticker("600519") == "600519"

    def test_lowercase_to_upper(self):
        """小写转大写 + strip。"""
        assert validate_ticker("vt") == "VT"
        # Note: "vt i" has a space in the middle — strip only removes
        # leading/trailing whitespace, so the space remains, triggering
        # invalid character detection. Test with valid tickers instead.
        assert validate_ticker("vti") == "VTI"

    def test_strip_whitespace(self):
        """strip 首尾空格。"""
        assert validate_ticker("  spy ") == "SPY"

    def test_hk_stock_five_digits(self):
        """港股 5 位代码。"""
        assert validate_ticker("00700") == "00700"


# ── 场景6：validate_ticker 非法 ──────────────────────────────────


class TestValidateTickerInvalid:
    """validate_ticker 非法输入。"""

    def test_empty_raises(self):
        """空字符串报错。"""
        with pytest.raises(ValueError):
            validate_ticker("")

    def test_non_string_raises(self):
        """非字符串报错。"""
        with pytest.raises(ValueError):
            validate_ticker(123)  # type: ignore[arg-type]

    def test_too_short_raises(self):
        """长度 <2 报错。"""
        with pytest.raises(ValueError):
            validate_ticker("A")

    def test_too_long_raises(self):
        """长度 >20 报错。"""
        with pytest.raises(ValueError):
            validate_ticker("A" * 21)

    def test_space_in_middle_raises(self):
        """含空格报错（strip 后再检查）。"""
        with pytest.raises(ValueError):
            validate_ticker("000 001")


# ── 场景7：is_valid_tx_id / is_valid_decision_id ────────────────


class TestIsValidId:
    """快速检查函数：is_valid_tx_id / is_valid_decision_id。"""

    def test_valid_tx_id_returns_true(self):
        """合法 tx ID 返回 True。"""
        assert is_valid_tx_id("tx-20250101-001") is True

    def test_invalid_tx_id_returns_false(self):
        """非法 tx ID 返回 False（不抛异常）。"""
        assert is_valid_tx_id("bad") is False

    def test_empty_tx_id_returns_false(self):
        """空字符串返回 False。"""
        assert is_valid_tx_id("") is False

    def test_valid_decision_id_returns_true(self):
        """合法决策 ID 返回 True。"""
        assert is_valid_decision_id("dec-20250101-005") is True

    def test_invalid_decision_id_returns_false(self):
        """非法决策 ID 返回 False。"""
        assert is_valid_decision_id("bad") is False

    def test_wrong_prefix_decision_id(self):
        """tx 前缀对决策 ID 返回 False。"""
        assert is_valid_decision_id("tx-20250101-001") is False


# ── 场景8：自定义前缀不在白名单 ──────────────────────────────────


class TestCustomPrefix:
    """自定义前缀不在 _VALID_PREFIXES。"""

    def test_custom_prefix_not_rejected(self):
        """validate_id('custom-abc', 'custom') 不报错（仅记录不拒绝）。"""
        result = validate_id("custom-abc", "custom")
        assert result == "custom-abc"

    def test_custom_prefix_with_valid_structure(self):
        """自定义前缀但格式正确。"""
        result = validate_id("myapp-001", "myapp")
        assert result == "myapp-001"

    def test_known_prefix_still_works(self):
        """已知前缀（tx）仍正常工作。"""
        result = validate_id("tx-20250101-001", "tx")
        assert result == "tx-20250101-001"
