"""
Praxis 纪律代价统计 + 元进化建议 (Meta-Evolution)
记录因拦截而错失的收益与规避的风险，月度审计时判断是否需要拓宽规则阈值

SSOT 原则：数据来自 outputs/logs/cost-log.jsonl，不在内存中维护第二份账目
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json


@dataclass
class InterceptionRecord:
    """拦截记录"""
    date: str
    ticker: str
    rule: str
    action: str  # "blocked_buy" | "blocked_sell"
    price_at_interception: float
    price_after_7d: Optional[float] = None
    opportunity_cost_pct: Optional[float] = None  # 错失的收益（正=错失上涨，负=规避下跌）
    risk_mitigated_pct: Optional[float] = None  # 规避的风险（正=规避下跌）


@dataclass
class DisciplineCostReport:
    """纪律代价报告"""
    period: str  # "2026-06"
    total_interceptions: int
    opportunity_cost_total: float  # 总错失收益
    risk_mitigated_total: float  # 总规避风险
    net_benefit: float  # 净收益 = 规避风险 - 错失收益
    interception_ratio: float  # 拦截收益比 = 规避风险 / 错失收益
    records: List[InterceptionRecord]
    meta_evolution_suggestion: Optional[str] = None


@dataclass
class MetaEvolutionResult:
    """元进化建议"""
    should_evolve: bool
    reason: str
    suggested_changes: List[str]  # 建议的规则调整
    confidence: float  # 0.0-1.0


class EvolutionEngine:
    """纪律代价统计 + 元进化引擎"""
    
    def __init__(self, logs_dir: str = "outputs/logs"):
        self.logs_dir = Path(logs_dir)
        self.interception_log = self.logs_dir / "interception_log.jsonl"
    
    def record_interception(self, record: InterceptionRecord):
        """记录一次拦截事件"""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        entry = {
            "date": record.date,
            "ticker": record.ticker,
            "rule": record.rule,
            "action": record.action,
            "price_at_interception": record.price_at_interception,
            "price_after_7d": record.price_after_7d,
            "opportunity_cost_pct": record.opportunity_cost_pct,
            "risk_mitigated_pct": record.risk_mitigated_pct,
        }
        
        with open(self.interception_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def load_records(self, period: str = None) -> List[InterceptionRecord]:
        """加载拦截记录"""
        if not self.interception_log.exists():
            return []
        
        records = []
        with open(self.interception_log, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                
                # 按期间过滤
                if period and not entry["date"].startswith(period):
                    continue
                
                records.append(InterceptionRecord(
                    date=entry["date"],
                    ticker=entry["ticker"],
                    rule=entry["rule"],
                    action=entry["action"],
                    price_at_interception=entry["price_at_interception"],
                    price_after_7d=entry.get("price_after_7d"),
                    opportunity_cost_pct=entry.get("opportunity_cost_pct"),
                    risk_mitigated_pct=entry.get("risk_mitigated_pct"),
                ))
        
        return records
    
    def calculate_discipline_cost(self, period: str) -> DisciplineCostReport:
        """
        计算某段时期的纪律代价。
        
        Args:
            period: 期间标识，如 "2026-06"
        
        Returns:
            DisciplineCostReport with statistics
        """
        records = self.load_records(period)
        
        if not records:
            return DisciplineCostReport(
                period=period,
                total_interceptions=0,
                opportunity_cost_total=0.0,
                risk_mitigated_total=0.0,
                net_benefit=0.0,
                interception_ratio=0.0,
                records=[],
                meta_evolution_suggestion="无拦截记录"
            )
        
        # 计算总错失收益和总规避风险
        opportunity_cost_total = sum(r.opportunity_cost_pct or 0 for r in records)
        risk_mitigated_total = sum(r.risk_mitigated_pct or 0 for r in records)
        
        # 净收益 = 规避风险 - 错失收益
        net_benefit = risk_mitigated_total - opportunity_cost_total
        
        # 拦截收益比 = 规避风险 / 错失收益（避免除零）
        if opportunity_cost_total > 0:
            interception_ratio = risk_mitigated_total / opportunity_cost_total
        else:
            interception_ratio = float('inf')  # 无错失收益，全部是规避风险
        
        # 元进化建议
        meta_evolution_suggestion = self._generate_evolution_suggestion(
            interception_ratio, net_benefit, len(records)
        )
        
        return DisciplineCostReport(
            period=period,
            total_interceptions=len(records),
            opportunity_cost_total=opportunity_cost_total,
            risk_mitigated_total=risk_mitigated_total,
            net_benefit=net_benefit,
            interception_ratio=interception_ratio,
            records=records,
            meta_evolution_suggestion=meta_evolution_suggestion
        )
    
    def _generate_evolution_suggestion(self, ratio: float, net_benefit: float,
                                       total_interceptions: int) -> str:
        """
        生成元进化建议。
        
        规则：
        - 拦截收益比 < 1.0 且 连续3个月 → 建议拓宽规则阈值
        - 拦收收益比 > 3.0 → 规则有效，保持不变
        - 净收益为负 → 需要人工审核
        """
        if total_interceptions < 3:
            return "样本不足（<3次），暂不建议元进化"
        
        if ratio < 1.0:
            return f"⚠️ 拦截收益比 {ratio:.2f} < 1.0：拦截导致的错失收益大于规避风险，建议拓宽规则阈值"
        elif ratio < 2.0:
            return f"拦截收益比 {ratio:.2f}，规则效果中性，建议保持现状并继续观察"
        elif ratio >= 3.0:
            return f"✅ 拦截收益比 {ratio:.2f} ≥ 3.0：规则有效，建议保持当前阈值"
        else:
            return f"拦截收益比 {ratio:.2f}，规则整体有效，建议保持现状"
    
    def check_meta_evolution(self, period: str) -> MetaEvolutionResult:
        """
        检查是否需要元进化。
        
        Returns:
            MetaEvolutionResult with should_evolve, reason, suggested_changes
        """
        report = self.calculate_discipline_cost(period)
        
        # 需要元进化的条件
        needs_evolution = (
            report.interception_ratio < 1.0
            and report.total_interceptions >= 5
            and report.net_benefit < 0
        )
        
        if needs_evolution:
            return MetaEvolutionResult(
                should_evolve=True,
                reason=f"拦截收益比 {report.interception_ratio:.2f} < 1.0，净收益 {report.net_benefit:.1f}% 为负",
                suggested_changes=[
                    "考虑将 Rule 2 持仓上限从 10% 放宽至 12%",
                    "考虑将 Rule 8 追高限制从 3% 放宽至 4%",
                    "需要人工审核并确认是否执行元进化"
                ],
                confidence=0.7
            )
        
        return MetaEvolutionResult(
            should_evolve=False,
            reason=report.meta_evolution_suggestion,
            suggested_changes=[],
            confidence=0.9
        )
    
    def generate_monthly_report(self, period: str) -> str:
        """
        生成月度纪律代价报告（去术语化）。
        
        Returns:
            Markdown 格式的报告
        """
        report = self.calculate_discipline_cost(period)
        evolution = self.check_meta_evolution(period)
        
        # 去术语化输出
        if report.net_benefit >= 0:
            benefit_emoji = "✅"
            benefit_text = f"规避风险 {report.risk_mitigated_total:.1f}% > 错失收益 {report.opportunity_cost_total:.1f}%"
        else:
            benefit_emoji = "⚠️"
            benefit_text = f"错失收益 {report.opportunity_cost_total:.1f}% > 规避风险 {report.risk_mitigated_total:.1f}%"
        
        md = f"""### 📊 纪律代价月度报告 ({period})

**本月拦截统计**：
- 拦截次数：{report.total_interceptions} 次
- 规避的风险：{report.risk_mitigated_total:.1f}%
- 错失的收益：{report.opportunity_cost_total:.1f}%
- 净收益：{benefit_emoji} {report.net_benefit:.1f}%（{benefit_text}）
- 拦截收益比：{report.interception_ratio:.2f}

**元进化建议**：
{report.meta_evolution_suggestion}
"""
        
        if evolution.should_evolve:
            md += f"\n**⚠️ 建议启动元进化**：\n"
            for change in evolution.suggested_changes:
                md += f"- {change}\n"
        
        return md


def main():
    """CLI 入口"""
    import argparse
    parser = argparse.ArgumentParser(description="纪律代价统计 + 元进化")
    parser.add_argument("--period", type=str, required=True, help="期间标识（如 2026-06）")
    parser.add_argument("--record", action="store_true", help="记录拦截事件")
    parser.add_argument("--ticker", type=str, help="标的代码")
    parser.add_argument("--rule", type=str, help="触发规则")
    parser.add_argument("--price", type=float, help="拦截时价格")
    args = parser.parse_args()
    
    engine = EvolutionEngine()
    
    if args.record:
        if not all([args.ticker, args.rule, args.price]):
            print("❌ 记录拦截事件需要 --ticker, --rule, --price")
            return
        
        record = InterceptionRecord(
            date=datetime.now().strftime("%Y-%m-%d"),
            ticker=args.ticker,
            rule=args.rule,
            action="blocked_buy",
            price_at_interception=args.price,
        )
        engine.record_interception(record)
        print(f"✅ 已记录拦截事件：{args.ticker} @ {args.price} ({args.rule})")
    else:
        report = engine.generate_monthly_report(args.period)
        print(report)


if __name__ == "__main__":
    main()
