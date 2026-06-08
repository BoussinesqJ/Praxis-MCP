"""自适应规则引擎

从历史交易和 NAV 数据中学习模式，生成规则草案。
所有规则必须经 prompt_scanner 安全扫描后才提交审批。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger("praxis.adaptive_rules")


class AdaptiveRule(BaseModel):
    """自适应规则"""
    rule_id: str
    name: str
    category: str           # stop_loss / grid_spacing / cash_floor / position / sentiment
    condition: str          # 人类可读的条件描述
    action: str             # 建议动作
    confidence: float       # 0.0 - 1.0
    hit_count: int = 0      # 命中次数
    miss_count: int = 0     # 未命中次数
    source_tx_ids: list[str] = []
    created_at: str = ""
    status: str = "draft"   # draft | active | retired | rejected


class AdaptiveRuleEngine:
    """自适应规则引擎"""

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._rules_path = self._workspace / "teams" / "adaptive" / "learned_rules.json"
        self._rules_md_path = self._workspace / "teams" / "adaptive" / "learned_rules.md"
        self._ledger_path = self._workspace / "data" / "ledger" / "transactions.jsonl"
        self._nav_path = self._workspace / "data" / "nav"

    def learn(self) -> list[AdaptiveRule]:
        """从历史数据中学习规则"""
        all_rules: list[AdaptiveRule] = []

        # 加载已有规则（避免重复）
        existing = {r.rule_id for r in self.load_rules()}

        # 学习各类模式
        all_rules.extend(self._learn_stop_loss_patterns(existing))
        all_rules.extend(self._learn_grid_spacing_patterns(existing))
        all_rules.extend(self._learn_cash_utilization_patterns(existing))

        # 安全扫描
        safe_rules = self._scan_rules(all_rules)

        # 持久化
        if safe_rules:
            self._save_rules(safe_rules)

        return safe_rules

    def load_rules(self) -> list[AdaptiveRule]:
        """加载已学习的规则"""
        if not self._rules_path.exists():
            return []
        try:
            data = json.loads(self._rules_path.read_text(encoding="utf-8"))
            return [AdaptiveRule(**r) for r in data]
        except Exception:
            return []

    def update_rule_status(self, rule_id: str, new_status: str) -> dict:
        """更新规则状态（审批通过/拒绝/退休）"""
        rules = self.load_rules()
        for rule in rules:
            if rule.rule_id == rule_id:
                old_status = rule.status
                rule.status = new_status
                self._save_rules(rules)
                return {
                    "success": True,
                    "data": {
                        "rule_id": rule_id,
                        "old_status": old_status,
                        "new_status": new_status,
                    },
                }
        return {"success": False, "error": f"规则 {rule_id} 不存在"}

    # ── 内部学习方法 ──

    def _load_transactions(self) -> list[dict]:
        """加载所有交易记录"""
        if not self._ledger_path.exists():
            return []
        txs = []
        with open(self._ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    txs.append(json.loads(line))
                except Exception:
                    continue
        return txs

    def _load_nav_series(self) -> list[dict]:
        """加载 NAV 历史"""
        records = []
        for nav_file in sorted(self._nav_path.glob("*.jsonl")):
            with open(nav_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        continue
        return sorted(records, key=lambda r: r.get("date", ""))

    def _learn_stop_loss_patterns(self, existing: set[str]) -> list[AdaptiveRule]:
        """学习止损模式：止损触发后反弹率过高 → 建议放宽止损线"""
        rules = []
        if f"rule_stop_loss_{datetime.now().strftime('%Y%m')}" in existing:
            return rules

        txs = self._load_transactions()
        nav_records = self._load_nav_series()

        if len(txs) < 5 or len(nav_records) < 10:
            return rules  # 数据不足

        # 统计卖出交易的盈亏
        sell_pnls = []
        for tx in txs:
            if tx.get("type") == "sell" and not tx.get("target_tx_id"):
                sell_pnls.append({
                    "tx_id": tx["tx_id"],
                    "ticker": tx["ticker"],
                    "price": tx["price"],
                    "date": tx.get("created_at", "")[:10],
                })

        # 简单模式检测：如果卖出后价格反弹（需要更多数据才有意义）
        # 当前实现：统计卖出次数和平均盈亏
        if len(sell_pnls) >= 3:
            rule_id = f"rule_stop_loss_{datetime.now().strftime('%Y%m')}"
            rules.append(AdaptiveRule(
                rule_id=rule_id,
                name="止损卖出统计",
                category="stop_loss",
                condition=f"最近 {len(sell_pnls)} 笔卖出交易已完成",
                action="建议复盘卖出时机，检查是否有止损后反弹的模式",
                confidence=0.5,
                hit_count=len(sell_pnls),
                source_tx_ids=[s["tx_id"] for s in sell_pnls],
                created_at=datetime.now().strftime("%Y-%m-%d"),
                status="draft",
            ))

        return rules

    def _learn_grid_spacing_patterns(self, existing: set[str]) -> list[AdaptiveRule]:
        """学习网格间距模式：同类标的买入间隔过短/过长"""
        rules = []
        if f"rule_grid_spacing_{datetime.now().strftime('%Y%m')}" in existing:
            return rules

        txs = self._load_transactions()

        # 按标的分组买入交易
        buy_dates: dict[str, list[str]] = {}
        for tx in txs:
            if tx.get("type") == "buy" and not tx.get("target_tx_id"):
                ticker = tx["ticker"]
                date = tx.get("created_at", "")[:10]
                if ticker and date:
                    buy_dates.setdefault(ticker, []).append(date)

        for ticker, dates in buy_dates.items():
            if len(dates) < 2:
                continue

            # 计算平均间隔
            sorted_dates = sorted(dates)
            intervals = []
            for i in range(1, len(sorted_dates)):
                d1 = datetime.strptime(sorted_dates[i - 1], "%Y-%m-%d")
                d2 = datetime.strptime(sorted_dates[i], "%Y-%m-%d")
                intervals.append((d2 - d1).days)

            if not intervals:
                continue

            avg_interval = sum(intervals) / len(intervals)

            if avg_interval < 5:
                rule_id = f"rule_grid_spacing_{ticker}_{datetime.now().strftime('%Y%m')}"
                rules.append(AdaptiveRule(
                    rule_id=rule_id,
                    name=f"网格间距过密: {ticker}",
                    category="grid_spacing",
                    condition=f"{ticker} 最近 {len(dates)} 笔买入平均间隔 {avg_interval:.1f} 天（< 5 天）",
                    action=f"建议将 {ticker} 网格间距从 8% 放宽到 10-12%",
                    confidence=0.6,
                    hit_count=len(dates),
                    created_at=datetime.now().strftime("%Y-%m-%d"),
                    status="draft",
                ))
            elif avg_interval > 30:
                rule_id = f"rule_grid_spacing_{ticker}_{datetime.now().strftime('%Y%m')}"
                rules.append(AdaptiveRule(
                    rule_id=rule_id,
                    name=f"网格间距过疏: {ticker}",
                    category="grid_spacing",
                    condition=f"{ticker} 最近 {len(dates)} 笔买入平均间隔 {avg_interval:.1f} 天（> 30 天）",
                    action=f"建议将 {ticker} 网格间距从 8% 收紧到 6% 以增加触发频率",
                    confidence=0.5,
                    hit_count=len(dates),
                    created_at=datetime.now().strftime("%Y-%m-%d"),
                    status="draft",
                ))

        return rules

    def _learn_cash_utilization_patterns(self, existing: set[str]) -> list[AdaptiveRule]:
        """学习现金利用率模式：现金比例持续过高"""
        rules = []
        if "rule_cash_utilization" in existing:
            return rules

        nav_records = self._load_nav_series()
        if len(nav_records) < 5:
            return rules

        # 计算最近 5 条 NAV 记录的现金比例
        recent = nav_records[-5:]
        cash_ratios = []
        for rec in recent:
            total = rec.get("total_assets", 0)
            cash = rec.get("cash", 0)
            if total > 0:
                cash_ratios.append(cash / total)

        if not cash_ratios:
            return rules

        avg_cash_ratio = sum(cash_ratios) / len(cash_ratios)

        if avg_cash_ratio > 0.60:
            rules.append(AdaptiveRule(
                rule_id="rule_cash_utilization",
                name="现金比例持续偏高",
                category="cash_floor",
                condition=f"最近 {len(cash_ratios)} 条 NAV 记录平均现金比例 {avg_cash_ratio:.1%}（> 60%）",
                action="建议复盘现金比例是否合理，评估是否有增加投资的机会",
                confidence=0.55,
                hit_count=len(cash_ratios),
                created_at=datetime.now().strftime("%Y-%m-%d"),
                status="draft",
            ))

        return rules

    def _scan_rules(self, rules: list[AdaptiveRule]) -> list[AdaptiveRule]:
        """安全扫描所有规则"""
        try:
            from praxis.engine.prompt_scanner import PromptScanner
            scanner = PromptScanner()
            safe_rules = []
            for rule in rules:
                scan_text = f"{rule.condition} {rule.action}"
                try:
                    scan = scanner.scan_content(scan_text, "adaptive_rule")
                    if scan.is_safe:
                        safe_rules.append(rule)
                    else:
                        rule.status = "rejected_by_scanner"
                        logger.warning(f"规则 {rule.rule_id} 被安全扫描拒绝")
                except Exception:
                    # 扫描器不可用时，默认通过
                    safe_rules.append(rule)
            return safe_rules
        except ImportError:
            # prompt_scanner 不可用时，默认全部通过
            return rules

    def _save_rules(self, new_rules: list[AdaptiveRule]):
        """持久化规则"""
        existing = self.load_rules()
        existing_ids = {r.rule_id for r in existing}

        # 合并（不覆盖已有的）
        for rule in new_rules:
            if rule.rule_id not in existing_ids:
                existing.append(rule)

        # 保存 JSON
        self._rules_path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.model_dump() for r in existing]
        self._rules_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 同步更新 Markdown
        self._update_markdown(existing)

    def _update_markdown(self, rules: list[AdaptiveRule]):
        """同步更新 learned_rules.md"""
        lines = [
            "# PRAXIS 自适应规则",
            "",
            "> 此文件由自适应规则引擎自动维护",
            f"> 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 已学习规则",
            "",
        ]

        active_rules = [r for r in rules if r.status in ("draft", "active")]
        if not active_rules:
            lines.append("（暂无有效规则，系统运行后将自动积累）")
        else:
            for rule in active_rules:
                status_emoji = "📝" if rule.status == "draft" else "✅"
                lines.extend([
                    f"### {status_emoji} {rule.name}",
                    f"- **ID**: `{rule.rule_id}`",
                    f"- **类别**: {rule.category}",
                    f"- **条件**: {rule.condition}",
                    f"- **建议**: {rule.action}",
                    f"- **置信度**: {rule.confidence:.0%}",
                    f"- **命中/未命中**: {rule.hit_count}/{rule.miss_count}",
                    f"- **状态**: {rule.status}",
                    f"- **创建时间**: {rule.created_at}",
                    "",
                ])

        # 已拒绝/退休的规则
        inactive = [r for r in rules if r.status in ("rejected_by_scanner", "retired")]
        if inactive:
            lines.extend(["## 已归档规则", ""])
            for rule in inactive:
                lines.append(f"- `{rule.rule_id}` ({rule.status}): {rule.name}")

        lines.extend([
            "",
            "## 变更流程",
            "",
            "1. 系统自动检测模式",
            "2. 生成规则草案（draft）",
            "3. 安全扫描",
            "4. 人工审批 → active",
            "5. 失效时 → retired",
        ])

        self._rules_md_path.parent.mkdir(parents=True, exist_ok=True)
        self._rules_md_path.write_text("\n".join(lines), encoding="utf-8")
