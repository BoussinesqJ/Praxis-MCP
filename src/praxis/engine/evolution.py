"""进化引擎 — 基于绩效数据的策略进化评估

核心职责：
1. 从策略配置读取进化维度
2. 结合绩效数据评估每个维度
3. 生成进化建议
4. 持久化进化记忆

从原版 engine/evolution.py + engine/evolution_memory.py 合并迁移。
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from praxis.core.exceptions import ConfigError
from praxis.core.interfaces import ConfigLoader


class EvolutionDimension(BaseModel):
    """进化维度 — 从原版 praxis.core.models.strategy 迁移"""
    name: str
    desc: str
    metric: str
    healthy_range: list[float] | None = None
    threshold: float | None = None


class EvolutionEngine:
    """进化引擎

    评估策略的健康度，基于预定义的进化维度。
    使用 workspace 路径定位配置和记忆存储。
    """

    def __init__(self, workspace: str = "."):
        self._workspace = Path(workspace)
        self._config_dir = self._workspace / "config" / "strategies"
        self._memory_dir = self._workspace / "data" / "evolution_memory"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    def evaluate(
        self,
        strategy_name: str,
        investor_id: str = "",
        portfolio_id: str = "",
        calculator=None,
        config_loader: ConfigLoader | None = None,
    ) -> dict:
        """评估进化维度

        Returns:
            {success, data: {strategy, dimensions, overall_health, ...}}
        """
        try:
            # 1. 从 YAML 读取进化维度（无 evolution_dimensions 则使用默认维度）
            evolution_dimensions = self._load_evolution_dimensions(strategy_name)

            # 2. 获取绩效指标
            metrics = {}
            if calculator:
                result = calculator.calculate(investor_id, portfolio_id)
                if isinstance(result, dict) and result.get("success"):
                    metrics = result.get("data", {})

            # 3. 评估每个维度
            dimension_results = []
            for dim in evolution_dimensions:
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

    def save_evaluation(self, strategy_name: str, evaluation: dict) -> str:
        """保存评估结果到 JSON

        Returns:
            str: 文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{strategy_name}_{timestamp}.json"
        path = self._memory_dir / filename

        record = {"strategy": strategy_name, **evaluation}
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def get_history(self, strategy_name: str = "", limit: int = 20) -> list[dict]:
        """读取历史评估记录

        Args:
            strategy_name: 策略名称（空字符串返回全部）
            limit: 返回记录数上限

        Returns:
            list[dict]: 评估记录列表（按时间倒序）
        """
        files = sorted(
            self._memory_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        results = []
        for f in files:
            if len(results) >= limit:
                break
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if not strategy_name or data.get("strategy", "") == strategy_name:
                    results.append(data)
            except Exception:
                continue

        return results

    # ── 内部方法 ──

    def _load_evolution_dimensions(self, strategy_name: str) -> list[EvolutionDimension]:
        """从策略 YAML 读取进化维度，无配置时返回默认维度"""
        path = self._config_dir / f"{strategy_name}.yaml"
        if not path.exists():
            raise ConfigError(f"策略文件不存在: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        dims_raw = data.get("evolution_dimensions", [])
        if not dims_raw:
            return _default_dimensions()

        return [EvolutionDimension(**d) for d in dims_raw if isinstance(d, dict)]

    @staticmethod
    def _evaluate_dimension(dim: EvolutionDimension, metrics: dict) -> dict:
        """评估单个维度"""
        current_value = _get_metric_value(dim.metric, metrics)
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

    @staticmethod
    def _generate_suggestions(dimensions: list[dict], metrics: dict) -> list[dict]:
        """生成进化建议"""
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


# ── 模块级辅助函数 ──

def _get_metric_value(metric_name: str, metrics) -> float:
    """从绩效指标中获取值（兼容 dict 和对象）"""
    if isinstance(metrics, dict):
        return float(metrics.get(metric_name, 0))
    if hasattr(metrics, metric_name):
        return float(getattr(metrics, metric_name, 0))
    return 0.0


def _default_dimensions() -> list[EvolutionDimension]:
    """无配置时的默认进化维度"""
    return [
        EvolutionDimension(
            name="return_efficiency",
            desc="收益率是否达到预期",
            metric="annualized_return",
            healthy_range=[0.05, 0.30],
            threshold=0.03,
        ),
        EvolutionDimension(
            name="risk_control",
            desc="最大回撤是否可控",
            metric="max_drawdown",
            healthy_range=[0.0, 0.20],
            threshold=0.25,
        ),
        EvolutionDimension(
            name="win_stability",
            desc="胜率是否稳定",
            metric="win_rate",
            healthy_range=[0.4, 0.8],
            threshold=0.3,
        ),
    ]
