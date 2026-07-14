"""tests for core/rule_mapping.py — 28 条规则三套编号双向映射."""

from __future__ import annotations

import pytest

from praxis.core.rule_mapping import RuleMapping, RuleDef


# ── 场景1：代码层 ID 正向解析 ─────────────────────────────────────


class TestResolveByRuleId:
    """resolve(代码层 ID) → 规则详情。"""

    def test_resolve_risk_cash_floor(self):
        """resolve("risk.cash_floor") 返回 8 字段 dict。"""
        result = RuleMapping.resolve("risk.cash_floor")
        assert result is not None
        assert result["rule_id"] == "risk.cash_floor"
        assert result["name"] == "现金底线"
        assert result["level"] == "hard_block"
        assert result["category"] == "risk"
        assert "description" in result
        assert "params" in result
        assert "doc_ref" in result
        assert len(result) == 8  # rule_id/doc_id/name/level/category/description/params/doc_ref

    def test_resolve_position_single_cap(self):
        """resolve("position.single_cap") 返回参数含 max_pct。"""
        result = RuleMapping.resolve("position.single_cap")
        assert result is not None
        assert result["rule_id"] == "position.single_cap"
        assert result["name"] == "单标的上限"
        assert result["level"] == "hard_block"
        assert result["params"] == {"max_pct": 30.0}


# ── 场景2：文档层编号解析 ─────────────────────────────────────────


class TestResolveByDocId:
    """resolve(文档层编号) → 规则详情。"""

    def test_resolve_int_1(self):
        """resolve(1) → '科创板禁入'。"""
        result = RuleMapping.resolve(1)
        assert result is not None
        assert result["name"] == "科创板禁入"
        assert result["rule_id"] == "risk.banned_market_star"
        assert result["level"] == "hard_block"

    def test_resolve_rule_5_string(self):
        """resolve("Rule 5") → '单标的上限'。"""
        result = RuleMapping.resolve("Rule 5")
        assert result is not None
        assert result["name"] == "单标的上限"
        assert result["rule_id"] == "position.single_cap"

    def test_resolve_int_28(self):
        """resolve(28) → '策略进化周期'。"""
        result = RuleMapping.resolve(28)
        assert result is not None
        assert result["name"] == "策略进化周期"
        assert result["rule_id"] == "strategy.evolution_cycle"
        assert result["level"] == "advisory"

    def test_resolve_by_doc_id_method(self):
        """get_by_doc_id(10) 与 resolve(10) 一致。"""
        assert RuleMapping.get_by_doc_id(10) == RuleMapping.resolve(10)

    def test_resolve_rule_string_format(self):
        """"Rule N" 格式和 int 格式结果一致。"""
        r1 = RuleMapping.resolve(3)
        r2 = RuleMapping.resolve("Rule 3")
        assert r1 is not None
        assert r1 == r2


# ── 场景3：不存在规则返回 None ────────────────────────────────────


class TestResolveNonexistent:
    """不存在规则的处理。"""

    def test_resolve_int_999(self):
        """resolve(999) → None。"""
        assert RuleMapping.resolve(999) is None

    def test_resolve_nonexistent_rule_id(self):
        """resolve("nonexistent.rule") → None。"""
        assert RuleMapping.resolve("nonexistent.rule") is None

    def test_resolve_rule_999_string(self):
        """resolve("Rule 999") → None。"""
        assert RuleMapping.resolve("Rule 999") is None

    def test_resolve_invalid_rule_string(self):
        """resolve("Rule abc") 非数字 → None。"""
        assert RuleMapping.resolve("Rule abc") is None

    def test_resolve_empty_string(self):
        """resolve("") → None。"""
        assert RuleMapping.resolve("") is None


# ── 场景4：批量解析 resolve_many ──────────────────────────────────


class TestResolveMany:
    """resolve_many 批量解析。"""

    def test_batch_resolve_existing(self):
        """传入已知 ID 列表返回对应规则。"""
        result = RuleMapping.resolve_many(
            ["risk.cash_floor", "position.single_cap"]
        )
        assert len(result) == 2
        assert "risk.cash_floor" in result
        assert "position.single_cap" in result

    def test_batch_with_nonexistent(self):
        """含不存在 ID 时仅返回存在的。"""
        result = RuleMapping.resolve_many(
            ["risk.cash_floor", "position.single_cap", "nonexistent"]
        )
        assert len(result) == 2
        assert "risk.cash_floor" in result
        assert "nonexistent" not in result

    def test_batch_all_nonexistent(self):
        """全部不存在返回空 dict。"""
        result = RuleMapping.resolve_many(["a.b", "c.d"])
        assert result == {}

    def test_batch_empty_list(self):
        """空列表返回空 dict。"""
        assert RuleMapping.resolve_many([]) == {}


# ── 场景5：按级别过滤 by_level ────────────────────────────────────


class TestByLevel:
    """by_level 按级别过滤。"""

    def test_hard_block_count(self):
        """hard_block 约 12 条。"""
        result = RuleMapping.by_level("hard_block")
        assert len(result) >= 10  # 约 12 条
        for r in result:
            assert r["level"] == "hard_block"

    def test_advisory_count(self):
        """advisory 约 7 条。"""
        result = RuleMapping.by_level("advisory")
        assert len(result) >= 6  # 约 7 条
        for r in result:
            assert r["level"] == "advisory"

    def test_soft_warning_count(self):
        """soft_warning 约 9 条。"""
        result = RuleMapping.by_level("soft_warning")
        assert len(result) >= 7
        for r in result:
            assert r["level"] == "soft_warning"

    def test_unknown_level_empty(self):
        """不存在的级别返回空列表。"""
        assert RuleMapping.by_level("nonexistent_level") == []


# ── 场景6：按分类过滤 by_category ─────────────────────────────────


class TestByCategory:
    """by_category 按分类过滤。"""

    def test_risk_category(self):
        """risk 分类约 8 条。"""
        result = RuleMapping.by_category("risk")
        assert len(result) >= 7
        for r in result:
            assert r["category"] == "risk"

    def test_process_category(self):
        """process 分类约 5 条。"""
        result = RuleMapping.by_category("process")
        assert len(result) >= 4
        for r in result:
            assert r["category"] == "process"

    def test_position_category(self):
        """position 分类约 4 条。"""
        result = RuleMapping.by_category("position")
        assert len(result) >= 3
        for r in result:
            assert r["category"] == "position"

    def test_unknown_category_empty(self):
        """不存在的分类返回空列表。"""
        assert RuleMapping.by_category("unknown_cat") == []


# ── 场景7：exists 存在性检查 ──────────────────────────────────────


class TestExists:
    """exists 存在性检查。"""

    def test_exists_rule_1(self):
        """exists("Rule 1") → True。"""
        assert RuleMapping.exists("Rule 1") is True

    def test_exists_risk_cash_floor(self):
        """exists("risk.cash_floor") → True。"""
        assert RuleMapping.exists("risk.cash_floor") is True

    def test_exists_int_1(self):
        """exists(1) → True。"""
        assert RuleMapping.exists(1) is True

    def test_exists_rule_999(self):
        """exists("Rule 999") → False。"""
        assert RuleMapping.exists("Rule 999") is False

    def test_exists_nonexistent(self):
        """exists("nonexistent") → False。"""
        assert RuleMapping.exists("nonexistent") is False


# ── 场景8：count + get_hard_blocks + list_all ─────────────────────


class TestAggregateMethods:
    """聚合查询方法。"""

    def test_count_equals_28(self):
        """count() == 28。"""
        assert RuleMapping.count() == 28

    def test_get_hard_blocks_returns_ids(self):
        """get_hard_blocks() 返回 hard_block 规则的代码层 ID 列表。"""
        blocks = RuleMapping.get_hard_blocks()
        assert len(blocks) >= 10
        assert "risk.cash_floor" in blocks
        assert "risk.stop_loss" in blocks
        # 全是字符串
        assert all(isinstance(b, str) for b in blocks)

    def test_list_all_returns_28(self):
        """list_all() 返回 28 条完整 dict。"""
        all_rules = RuleMapping.list_all()
        assert len(all_rules) == 28
        for r in all_rules:
            assert "rule_id" in r
            assert "doc_id" in r
            assert "name" in r

    def test_get_by_doc_id_28(self):
        """get_by_doc_id(28) 返回 '策略进化周期'。"""
        result = RuleMapping.get_by_doc_id(28)
        assert result is not None
        assert result["name"] == "策略进化周期"
        assert result["rule_id"] == "strategy.evolution_cycle"

    def test_list_all_consistency(self):
        """list_all 返回的数据与 count 一致。"""
        assert len(RuleMapping.list_all()) == RuleMapping.count()
