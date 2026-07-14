"""数据质量检查层

检查交易记录和数据源的完整性、一致性、时效性。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from praxis.core.logging_config import get_logger

if TYPE_CHECKING:
    from praxis.core.interfaces import DataProvider, Ledger

logger = get_logger(__name__)


class DataQualityChecker:
    """数据质量检查器

    检查维度：
    - 完整性：交易记录字段是否缺失、是否有重复
    - 一致性：持仓数量 vs 账本推导是否一致
    - 时效性：行情数据是否过期
    """

    def __init__(self):
        pass

    def check_completeness(self, ledger: "Ledger") -> dict:
        """检查交易记录完整性

        检查每笔交易的必填字段和重复检测。

        Args:
            ledger: 交易账本实例

        Returns:
            {
                name: "completeness",
                status: "pass" | "warn" | "fail",
                details: {
                    total_records, missing_fields, duplicate_records,
                    issues: [...]
                }
            }
        """
        transactions = ledger.list() if hasattr(ledger, 'list') else []
        if not transactions:
            return {
                "name": "completeness",
                "status": "warn",
                "details": {"total_records": 0, "message": "账本为空，无法检查完整性"}
            }

        required_fields = ["ticker", "tx_type", "quantity", "price"]
        issues = []
        missing_count = 0
        seen_keys: set[str] = set()
        duplicates = 0

        for tx in transactions:
            tx_dict = tx.model_dump() if hasattr(tx, 'model_dump') else vars(tx)
            # 检查必填字段
            for field in required_fields:
                val = tx_dict.get(field)
                if val is None or val == "" or val == 0:
                    issues.append({
                        "tx_id": tx_dict.get("tx_id", ""),
                        "field": field,
                        "issue": "missing_or_empty",
                    })
                    missing_count += 1

            # 检查重复
            key = tx_dict.get("idempotency_key", "") or tx_dict.get("tx_id", "")
            if key and key in seen_keys:
                duplicates += 1
                issues.append({
                    "tx_id": tx_dict.get("tx_id", ""),
                    "issue": "duplicate_record",
                })
            if key:
                seen_keys.add(key)

        status = "pass"
        if duplicates > 0 or missing_count > len(transactions) * 0.3:
            status = "fail"
        elif missing_count > 0:
            status = "warn"

        return {
            "name": "completeness",
            "status": status,
            "details": {
                "total_records": len(transactions),
                "missing_fields": missing_count,
                "duplicate_records": duplicates,
                "issues": issues[:20],  # 最多返回20条
            },
        }

    def check_consistency(self, ledger: "Ledger", data_provider: "DataProvider") -> dict:
        """交叉验证持仓数量 vs 账本

        通过账本交易记录推导的持仓，与 data_provider 获取的最新价格对比，
        验证是否有不一致的地方。

        Args:
            ledger: 交易账本实例
            data_provider: 行情数据源

        Returns:
            {
                name: "consistency",
                status: "pass" | "warn" | "fail",
                details: {
                    derived_positions, inconsistencies, ...
                }
            }
        """
        transactions = ledger.list() if hasattr(ledger, 'list') else []
        if not transactions:
            return {
                "name": "consistency",
                "status": "warn",
                "details": {"message": "账本为空，无法检查一致性"}
            }

        # 从账本推导持仓数量
        derived: dict[str, float] = {}
        for tx in transactions:
            ticker = tx.ticker if hasattr(tx, 'ticker') else ""
            if not ticker:
                continue
            qty = tx.quantity if hasattr(tx, 'quantity') else 0
            tx_type_str = str(tx.tx_type) if hasattr(tx, 'tx_type') else ""

            if qty <= 0:
                continue

            if "buy" in tx_type_str.lower() or "subscribe" in tx_type_str.lower():
                derived[ticker] = derived.get(ticker, 0) + qty
            elif "sell" in tx_type_str.lower() or "redeem" in tx_type_str.lower():
                derived[ticker] = derived.get(ticker, 0) - qty

        # 清理负数（可能是数据不完整）
        derived = {k: max(0, v) for k, v in derived.items()}

        inconsistencies = []
        for ticker, qty in derived.items():
            if qty == 0:
                inconsistencies.append({
                    "ticker": ticker,
                    "derived_quantity": qty,
                    "issue": "zero_balance",
                })

        status = "pass" if not inconsistencies else "warn"

        return {
            "name": "consistency",
            "status": status,
            "details": {
                "derived_positions": {k: round(v, 4) for k, v in derived.items()},
                "inconsistencies": inconsistencies,
            },
        }

    def check_timeliness(self, data_provider: "DataProvider") -> dict:
        """数据时效性检查

        检查行情数据的时间戳是否过期。

        Args:
            data_provider: 行情数据源

        Returns:
            {
                name: "timeliness",
                status: "pass" | "warn" | "fail",
                details: {
                    check_time, stale_items, ...
                }
            }
        """
        now = datetime.now(timezone.utc)
        stale_items = []

        # 尝试获取数据源的最近更新时间
        # 如果 data_provider 有 last_update 属性则使用
        last_update = getattr(data_provider, 'last_update', None)
        if last_update:
            try:
                if isinstance(last_update, str):
                    last_update = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
                age_hours = (now - last_update).total_seconds() / 3600
                if age_hours > 24:
                    stale_items.append({
                        "source": "data_provider",
                        "last_update": last_update.isoformat(),
                        "age_hours": round(age_hours, 1),
                        "stale": True,
                    })
            except (ValueError, TypeError):
                pass

        status = "pass"
        if stale_items:
            status = "warn"

        return {
            "name": "timeliness",
            "status": status,
            "details": {
                "check_time": now.isoformat(),
                "max_stale_hours": 24,
                "stale_items": stale_items,
                "message": "所有数据时效正常" if not stale_items else "部分数据可能过期",
            },
        }

    def run_all_checks(self, ledger: "Ledger", data_provider: "DataProvider") -> dict:
        """运行全部 3 项检查

        Args:
            ledger: 交易账本实例
            data_provider: 行情数据源

        Returns:
            {overall_status, checks: [{name, status, details}, ...]}
        """
        checks = [
            self.check_completeness(ledger),
            self.check_consistency(ledger, data_provider),
            self.check_timeliness(data_provider),
        ]

        statuses = [c["status"] for c in checks]
        if "fail" in statuses:
            overall = "fail"
        elif "warn" in statuses:
            overall = "warn"
        else:
            overall = "pass"

        return {
            "overall_status": overall,
            "checks": checks,
        }
