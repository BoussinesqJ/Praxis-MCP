"""进化引擎（GPT 架构底线：基于绩效数据，非事后叙事）

核心职责：
1. 从策略模板读取进化维度
2. 结合绩效数据评估每个维度
3. 生成进化建议（基于数据，非凭感觉）
4. 安全约束：修改需审批+备份+Diff终审
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from praxis.engine.config_loader import YamlConfigLoader
from praxis.engine.performance import EnhancedPerformanceCalculator
from praxis.core.ledger import FileLedger
from praxis.core.models.strategy import EvolutionDimension
from praxis.core.models.error import PraxisError


class EvolutionEngine:
    """进化引擎"""

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._config = YamlConfigLoader(workspace)
        self._ledger = FileLedger(workspace + "/data/ledger/transactions.jsonl")

    def evaluate(
        self,
        strategy_name: str,
        investor_id: str,
        portfolio_id: str,
    ) -> dict:
        """评估进化维度

        Returns:
            {
                "strategy": strategy_name,
                "dimensions": [
                    {
                        "name": "grid_spacing",
                        "desc": "网格间距是否过密或过疏",
                        "metric": "avg_days_between_triggers",
                        "current_value": 12.5,
                        "healthy_range": [5, 30],
                        "status": "healthy" | "warning" | "critical",
                        "recommendation": "..."
                    },
                    ...
                ],
                "overall_health": "healthy" | "warning" | "critical",
                "evolution_suggestions": [...]
            }
        """
        try:
            # 1. 加载策略模板
            strategy = self._config.load_strategy(strategy_name)

            # 2. 计算绩效指标
            calculator = EnhancedPerformanceCalculator(self._ledger)
            metrics = calculator.calculate(investor_id, portfolio_id)

            # 3. 评估每个进化维度
            dimension_results = []
            for dim in strategy.evolution_dimensions:
                result = self._evaluate_dimension(dim, metrics)
                dimension_results.append(result)

            # 4. 计算整体健康度
            statuses = [d["status"] for d in dimension_results]
            if "critical" in statuses:
                overall_health = "critical"
            elif "warning" in statuses:
                overall_health = "warning"
            else:
                overall_health = "healthy"

            # 5. 生成进化建议
            suggestions = self._generate_suggestions(dimension_results, metrics)

            return {
                "success": True,
                "data": {
                    "strategy": strategy_name,
                    "investor": investor_id,
                    "portfolio": portfolio_id,
                    "dimensions": dimension_results,
                    "overall_health": overall_health,
                    "evolution_suggestions": suggestions,
                    "metrics": metrics,
                    "evaluated_at": datetime.now(timezone.utc).isoformat(),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _evaluate_dimension(
        self, dim: EvolutionDimension, metrics: dict
    ) -> dict:
        """评估单个进化维度"""
        # 根据 metric 名称获取当前值
        current_value = self._get_metric_value(dim.metric, metrics)

        # 判断状态
        status = "healthy"
        recommendation = ""

        if dim.healthy_range:
            low, high = dim.healthy_range
            if current_value < low:
                status = "warning"
                recommendation = f"当前值 {current_value:.2f} 低于健康范围 [{low}, {high}]"
            elif current_value > high:
                status = "warning"
                recommendation = f"当前值 {current_value:.2f} 高于健康范围 [{low}, {high}]"
            else:
                recommendation = f"当前值 {current_value:.2f} 在健康范围内 [{low}, {high}]"

        if dim.threshold is not None:
            if current_value < dim.threshold:
                status = "critical"
                recommendation = f"当前值 {current_value:.2f} 低于阈值 {dim.threshold}"

        return {
            "name": dim.name,
            "desc": dim.desc,
            "metric": dim.metric,
            "current_value": current_value,
            "healthy_range": dim.healthy_range,
            "threshold": dim.threshold,
            "status": status,
            "recommendation": recommendation,
        }

    def _get_metric_value(self, metric_name: str, metrics) -> float:
        """从绩效指标中获取值"""
        # 支持 PerformanceMetrics 对象和 dict
        if hasattr(metrics, metric_name):
            return getattr(metrics, metric_name, 0)
        elif isinstance(metrics, dict):
            return metrics.get(metric_name, 0)
        return 0

    def _generate_suggestions(
        self, dimensions: list[dict], metrics: dict
    ) -> list[dict]:
        """生成进化建议（基于数据，非事后叙事）"""
        suggestions = []

        for dim in dimensions:
            if dim["status"] == "critical":
                suggestions.append({
                    "priority": "high",
                    "dimension": dim["name"],
                    "suggestion": f"紧急：{dim['desc']}，{dim['recommendation']}",
                    "action": "需要立即调整",
                })
            elif dim["status"] == "warning":
                suggestions.append({
                    "priority": "medium",
                    "dimension": dim["name"],
                    "suggestion": f"警告：{dim['desc']}，{dim['recommendation']}",
                    "action": "建议观察并准备调整",
                })

        return suggestions

    def format_evaluation(self, result: dict) -> str:
        """格式化评估结果"""
        if not result.get("success"):
            return f"评估失败: {result.get('error')}"

        data = result["data"]
        lines = [
            "=== 进化维度评估 ===",
            f"策略: {data['strategy']}",
            f"投资者: {data['investor']}",
            f"组合: {data['portfolio']}",
            f"评估时间: {data['evaluated_at']}",
            "",
            f"整体健康度: {data['overall_health'].upper()}",
            "",
            "--- 维度详情 ---",
        ]

        for dim in data["dimensions"]:
            status_icon = {"healthy": "✓", "warning": "⚠", "critical": "✗"}.get(
                dim["status"], "?"
            )
            lines.append(f"  {status_icon} {dim['name']}: {dim['desc']}")
            lines.append(f"    当前值: {dim['current_value']:.2f}")
            if dim["healthy_range"]:
                lines.append(f"    健康范围: {dim['healthy_range']}")
            if dim["threshold"]:
                lines.append(f"    阈值: {dim['threshold']}")
            lines.append(f"    评估: {dim['recommendation']}")
            lines.append("")

        if data["evolution_suggestions"]:
            lines.append("--- 进化建议 ---")
            for suggestion in data["evolution_suggestions"]:
                lines.append(f"  [{suggestion['priority'].upper()}] {suggestion['suggestion']}")
                lines.append(f"    建议动作: {suggestion['action']}")

        return "\n".join(lines)

    def backup_strategy(self, strategy_name: str) -> str:
        """备份策略文件（GPT 架构底线：修改前自动备份）"""
        strategy_path = self._workspace / "strategies" / f"{strategy_name}.yaml"
        if not strategy_path.exists():
            raise PraxisError(f"策略文件不存在: {strategy_path}")

        # 创建备份
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = strategy_path.with_suffix(f".{timestamp}.bak")
        shutil.copy2(strategy_path, backup_path)

        return str(backup_path)
