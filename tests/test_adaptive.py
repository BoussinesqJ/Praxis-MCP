"""Tests for adaptive rules engine"""
import json
import pytest
from pathlib import Path

import yaml

from praxis.engine.adaptive_rules import AdaptiveRuleEngine, AdaptiveRule


@pytest.fixture
def ws(tmp_path):
    """创建有交易记录和 NAV 历史的 workspace"""
    # 创建投资者
    inv_dir = tmp_path / "investors" / "test_user" / "portfolios" / "test_port"
    inv_dir.mkdir(parents=True)
    (tmp_path / "investors" / "test_user" / "profile.yaml").write_text(
        yaml.dump({"investor": {"name": "test", "risk_level": "C3", "capital_cny": 100000}}),
        encoding="utf-8",
    )
    (inv_dir / "portfolio.yaml").write_text(
        yaml.dump({"portfolio": {"strategy_type": "grid_value"}}),
        encoding="utf-8",
    )

    # 创建交易记录
    ledger_dir = tmp_path / "data" / "ledger"
    ledger_dir.mkdir(parents=True)
    txs = [
        {"tx_id": f"tx-{i:03d}", "type": "buy", "ticker": "600995", "quantity": 100,
         "price": 14.0 + i * 0.5, "fee": 0, "created_at": f"2026-06-{i+1:02d}T10:00:00Z",
         "status": "confirmed", "tags": ["real"]}
        for i in range(1, 8)
    ]
    txs.extend([
        {"tx_id": "tx-sell-001", "type": "sell", "ticker": "600995", "quantity": 100,
         "price": 16.35, "fee": 0, "created_at": "2026-06-08T10:00:00Z",
         "status": "confirmed", "tags": ["real"]},
        {"tx_id": "tx-sell-002", "type": "sell", "ticker": "600995", "quantity": 100,
         "price": 15.50, "fee": 0, "created_at": "2026-06-09T10:00:00Z",
         "status": "confirmed", "tags": ["real"]},
        {"tx_id": "tx-sell-003", "type": "sell", "ticker": "600995", "quantity": 100,
         "price": 17.00, "fee": 0, "created_at": "2026-06-10T10:00:00Z",
         "status": "confirmed", "tags": ["real"]},
    ])
    with open(ledger_dir / "transactions.jsonl", "w", encoding="utf-8") as f:
        for tx in txs:
            f.write(json.dumps(tx, ensure_ascii=False) + "\n")

    # 创建 NAV 历史
    nav_dir = tmp_path / "data" / "nav"
    nav_dir.mkdir(parents=True)
    navs = [
        {"date": f"2026-06-{i+1:02d}", "nav": 1.0, "total_assets": 100000,
         "positions_value": 7000, "cash": 93000}
        for i in range(10)
    ]
    with open(nav_dir / "default.jsonl", "w", encoding="utf-8") as f:
        for nav in navs:
            f.write(json.dumps(nav) + "\n")

    # 创建 adaptive 目录
    (tmp_path / "teams" / "adaptive").mkdir(parents=True)
    (tmp_path / "teams" / "adaptive" / "learned_rules.md").write_text(
        "# 自适应规则\n\n（暂无）\n", encoding="utf-8"
    )

    return tmp_path


class TestLearnRules:
    """规则学习测试"""

    def test_learn_returns_rules(self, ws):
        """学习应返回规则列表"""
        engine = AdaptiveRuleEngine(str(ws))
        rules = engine.learn()
        assert isinstance(rules, list)

    def test_learn_generates_sell_pattern(self, ws):
        """有卖出交易时应生成止损/卖出统计规则"""
        engine = AdaptiveRuleEngine(str(ws))
        rules = engine.learn()
        # 应该有卖出统计规则
        sell_rules = [r for r in rules if r.category == "stop_loss"]
        assert len(sell_rules) >= 1

    def test_learn_generates_grid_spacing(self, ws):
        """买入间隔过短时应生成网格间距规则"""
        engine = AdaptiveRuleEngine(str(ws))
        rules = engine.learn()
        # 7 笔买入在 7 天内，平均间隔 1 天，应触发过密规则
        grid_rules = [r for r in rules if r.category == "grid_spacing"]
        assert len(grid_rules) >= 1
        assert "过密" in grid_rules[0].name

    def test_learn_generates_cash_utilization(self, ws):
        """现金比例 > 60% 时应生成现金利用率规则"""
        engine = AdaptiveRuleEngine(str(ws))
        rules = engine.learn()
        cash_rules = [r for r in rules if r.category == "cash_floor"]
        assert len(cash_rules) >= 1

    def test_learn_saves_rules(self, ws):
        """学习后规则应持久化"""
        engine = AdaptiveRuleEngine(str(ws))
        engine.learn()
        rules_file = ws / "teams" / "adaptive" / "learned_rules.json"
        assert rules_file.exists()
        data = json.loads(rules_file.read_text(encoding="utf-8"))
        assert len(data) > 0

    def test_learn_updates_markdown(self, ws):
        """学习后 Markdown 文件应更新"""
        engine = AdaptiveRuleEngine(str(ws))
        engine.learn()
        md_file = ws / "teams" / "adaptive" / "learned_rules.md"
        content = md_file.read_text(encoding="utf-8")
        assert "自适应规则引擎自动维护" in content

    def test_no_duplicate_rules(self, ws):
        """多次学习不应产生重复规则"""
        engine = AdaptiveRuleEngine(str(ws))
        engine.learn()
        engine.learn()  # 第二次
        rules = engine.load_rules()
        rule_ids = [r.rule_id for r in rules]
        assert len(rule_ids) == len(set(rule_ids))


class TestRuleStatus:
    """规则状态管理测试"""

    def test_approve_rule(self, ws):
        """审批规则: draft → active"""
        engine = AdaptiveRuleEngine(str(ws))
        engine.learn()
        rules = engine.load_rules()
        draft = next((r for r in rules if r.status == "draft"), None)
        if draft:
            result = engine.update_rule_status(draft.rule_id, "active")
            assert result["success"] is True
            assert result["data"]["new_status"] == "active"

    def test_reject_rule(self, ws):
        """拒绝规则"""
        engine = AdaptiveRuleEngine(str(ws))
        engine.learn()
        rules = engine.load_rules()
        draft = next((r for r in rules if r.status == "draft"), None)
        if draft:
            result = engine.update_rule_status(draft.rule_id, "rejected_by_scanner")
            assert result["success"] is True

    def test_retire_rule(self, ws):
        """退休规则: active → retired"""
        engine = AdaptiveRuleEngine(str(ws))
        engine.learn()
        rules = engine.load_rules()
        if rules:
            rule = rules[0]
            engine.update_rule_status(rule.rule_id, "active")
            result = engine.update_rule_status(rule.rule_id, "retired")
            assert result["success"] is True
            assert result["data"]["new_status"] == "retired"

    def test_nonexistent_rule(self, ws):
        """不存在的规则 ID"""
        engine = AdaptiveRuleEngine(str(ws))
        result = engine.update_rule_status("nonexistent_id", "active")
        assert result["success"] is False


class TestEmptyData:
    """空数据场景"""

    def test_empty_workspace(self, tmp_path):
        """空 workspace 不应报错"""
        engine = AdaptiveRuleEngine(str(tmp_path))
        rules = engine.learn()
        assert rules == []

    def test_no_transactions(self, tmp_path):
        """无交易记录不应报错"""
        (tmp_path / "teams" / "adaptive").mkdir(parents=True)
        engine = AdaptiveRuleEngine(str(tmp_path))
        rules = engine.learn()
        assert rules == []
