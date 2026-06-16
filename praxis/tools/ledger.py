"""MCP 工具 - 交易账本"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from praxis.core.ledger import FileLedger
from praxis.core.models.transaction import Transaction, TransactionType, TransactionStatus


def _get_ledger(workspace: str = ".") -> FileLedger:
    """获取账本实例"""
    ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"
    return FileLedger(ledger_path)


def _atomic_rewrite_jsonl(path: Path, records: list[Transaction]):
    """原子重写 JSONL 文件（temp → fsync → replace）"""
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            for tx in records:
                f.write(tx.to_jsonl() + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise e




def get_ledger(ticker: str | None = None, limit: int = 100, workspace: str = ".") -> dict:
    """查询交易记录"""
    try:
        ledger = _get_ledger(workspace)
        transactions = ledger.list(ticker=ticker, limit=limit)
        return {
            "success": True,
            "data": {
                "total": ledger.count(),
                "transactions": [tx.model_dump(mode="json") for tx in transactions],
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def add_transaction(
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    fee: float = 0,
    decision_id: str | None = None,
    idempotency_key: str | None = None,
    auto_approve: bool = False,
    tags: list[str] | None = None,
    asset_type: str | None = None,
    workspace: str = ".",
) -> dict:
    """添加交易记录

    GPT 架构底线：
    - 幂等键防重复
    - 默认需审批（auto_approve=False）
    - 审批后才写入账本
    """
    try:
        # 映射 action → TransactionType
        type_map = {
            "buy": TransactionType.BUY,
            "sell": TransactionType.SELL,
            "subscribe": TransactionType.SUBSCRIBE,
            "redeem": TransactionType.REDEEM,
            "dividend": TransactionType.DIVIDEND,
        }
        tx_type = type_map.get(action)
        if not tx_type:
            return {"success": False, "error": f"不支持的交易类型: {action}"}

        # 验证决策 ID 存在性（引用完整性）
        if decision_id:
            from praxis.tools.decision import get_decision_record
            decision_check = get_decision_record(decision_id, workspace)
            if not decision_check.get("success"):
                return {"success": False, "error": f"决策 {decision_id} 不存在，请先创建决策记录"}

        # 创建交易记录
        tx = Transaction(
            tx_id="",  # 由 ledger 生成
            type=tx_type,
            ticker=ticker,
            quantity=quantity,
            price=price,
            fee=fee,
            decision_id=decision_id,
            idempotency_key=idempotency_key,
            status=TransactionStatus.CONFIRMED if auto_approve else TransactionStatus.PENDING,
            tags=tags or [],
            asset_type=asset_type,
        )

        if auto_approve:
            # 自动审批：直接写入账本
            ledger = _get_ledger(workspace)
            tx_id = ledger.append(tx)

            # 事件驱动：交易完成后触发进化评估（非阻塞）
            _trigger_post_transaction(workspace, ticker, action)

            return {
                "success": True,
                "data": {
                    "status": "confirmed",
                    "tx_id": tx_id,
                    "message": f"交易已确认: {action} {ticker} {quantity}@{price}",
                },
            }
        else:
            # 需审批：写入 pending 列表
            pending_path = Path(workspace) / "data" / "ledger" / "pending.jsonl"
            pending_path.parent.mkdir(parents=True, exist_ok=True)

            # 生成 pending tx_id
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            pending_count = 0
            if pending_path.exists():
                with open(pending_path, "r", encoding="utf-8") as f:
                    pending_count = sum(1 for line in f if line.strip())
            temp_tx_id = f"tx-{today}-pending-{pending_count + 1:03d}"
            tx.tx_id = temp_tx_id

            # 追加写入 pending 文件（append 是安全的）
            with open(pending_path, "a", encoding="utf-8") as f:
                f.write(tx.to_jsonl() + "\n")
                f.flush()

            return {
                "success": True,
                "data": {
                    "status": "pending_approval",
                    "tx_id": temp_tx_id,
                    "transaction": tx.model_dump(mode="json"),
                    "message": f"交易待审批: {action} {ticker} {quantity}@{price}，请确认后调用 approve_transaction",
                },
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def approve_transaction(tx_id: str, workspace: str = ".") -> dict:
    """审批通过交易（从 pending 写入账本）"""
    try:
        pending_path = Path(workspace) / "data" / "ledger" / "pending.jsonl"
        if not pending_path.exists():
            return {"success": False, "error": "没有待审批的交易"}

        # 读取所有 pending 记录，分离目标和其他
        pending_txs: list[Transaction] = []
        target_tx = None
        with open(pending_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    tx = Transaction(**data)
                    if tx.tx_id == tx_id:
                        target_tx = tx
                    else:
                        pending_txs.append(tx)
                except Exception:
                    continue

        if not target_tx:
            return {"success": False, "error": f"待审批交易 {tx_id} 不存在"}

        # 写入正式账本
        target_tx.status = TransactionStatus.CONFIRMED
        ledger = _get_ledger(workspace)
        target_tx.tx_id = ""  # 让 ledger 生成正式 ID
        new_tx_id = ledger.append(target_tx)

        # 原子重写 pending 文件（移除已审批的）
        _atomic_rewrite_jsonl(pending_path, pending_txs)

        # 事件驱动：审批通过后触发进化评估
        _trigger_post_transaction(workspace, target_tx.ticker, target_tx.type.value)

        return {
            "success": True,
            "data": {
                "status": "confirmed",
                "tx_id": new_tx_id,
                "message": f"交易 {tx_id} 已审批通过，写入账本: {new_tx_id}",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def reject_transaction(tx_id: str, reason: str, workspace: str = ".") -> dict:
    """拒绝交易"""
    try:
        pending_path = Path(workspace) / "data" / "ledger" / "pending.jsonl"
        if not pending_path.exists():
            return {"success": False, "error": "没有待审批的交易"}

        pending_txs: list[Transaction] = []
        target_tx = None
        with open(pending_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    tx = Transaction(**data)
                    if tx.tx_id == tx_id:
                        target_tx = tx
                    else:
                        pending_txs.append(tx)
                except Exception:
                    continue

        if not target_tx:
            return {"success": False, "error": f"待审批交易 {tx_id} 不存在"}

        # 原子重写 pending 文件（移除已拒绝的）
        _atomic_rewrite_jsonl(pending_path, pending_txs)

        return {
            "success": True,
            "data": {
                "status": "rejected",
                "tx_id": tx_id,
                "reason": reason,
                "message": f"交易 {tx_id} 已拒绝: {reason}",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_pending_transactions(workspace: str = ".") -> dict:
    """列出所有待审批的交易"""
    try:
        pending_path = Path(workspace) / "data" / "ledger" / "pending.jsonl"
        if not pending_path.exists():
            return {"success": True, "data": {"total": 0, "transactions": []}}

        pending_txs = []
        with open(pending_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    tx = Transaction(**data)
                    pending_txs.append(tx.model_dump(mode="json"))
                except Exception:
                    continue

        return {
            "success": True,
            "data": {
                "total": len(pending_txs),
                "transactions": pending_txs,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def reverse_transaction(tx_id: str, reason: str, workspace: str = ".") -> dict:
    """反向冲销（GPT 架构底线：错误用冲销，不用覆盖）"""
    try:
        ledger = _get_ledger(workspace)
        new_tx_id = ledger.reverse(tx_id, reason)
        return {
            "success": True,
            "data": {
                "original_tx_id": tx_id,
                "correction_tx_id": new_tx_id,
                "message": f"已冲销 {tx_id}，冲销记录: {new_tx_id}",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_transaction(tx_id: str, workspace: str = ".") -> dict:
    """物理删除单条交易记录（重写文件）

    警告：破坏 append-only 语义，仅用于清理测试/错误数据。
    """
    try:
        ledger = _get_ledger(workspace)
        if ledger.delete(tx_id):
            return {
                "success": True,
                "data": {"message": f"已物理删除交易 {tx_id}"},
            }
        return {"success": False, "error": f"交易 {tx_id} 不存在"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def purge_ledger(tag: str | None = None, confirm: bool = False, workspace: str = ".") -> dict:
    """清空交易账本（按标签或全部）

    Args:
        tag: 如果指定，仅删除带有该标签的记录；None 则清空全部
        confirm: 必须为 True 才执行
    """
    if not confirm:
        return {
            "success": False,
            "error": "安全确认：请设置 confirm=true 以执行清除操作",
        }
    try:
        ledger = _get_ledger(workspace)
        count = ledger.purge(tag=tag)
        scope = f"标签 '{tag}' 的" if tag else "全部"
        return {
            "success": True,
            "data": {
                "deleted_count": count,
                "message": f"已清除 {scope}交易记录 {count} 条",
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _trigger_post_transaction(workspace: str, ticker: str, action: str):
    """交易完成后触发进化评估和规则学习（非阻塞，失败不影响交易结果）"""
    try:
        from praxis.tools.evolution import auto_evolve
        # 尝试获取策略名称（从 portfolio 配置）
        from praxis.engine.config_loader import YamlConfigLoader
        loader = YamlConfigLoader(workspace)
        # 扫描投资者目录获取默认策略
        investors_dir = Path(workspace) / "investors"
        for inv_dir in sorted(investors_dir.iterdir()):
            if not inv_dir.is_dir() or inv_dir.name.startswith(("_", ".")):
                continue
            profile_path = inv_dir / "profile.yaml"
            if not profile_path.exists():
                continue
            # 找到第一个 portfolio
            portfolios_dir = inv_dir / "portfolios"
            if not portfolios_dir.exists():
                continue
            for port_dir in sorted(portfolios_dir.iterdir()):
                if not port_dir.is_dir():
                    continue
                port_path = port_dir / "portfolio.yaml"
                if not port_path.exists():
                    continue
                import yaml
                pdata = yaml.safe_load(port_path.read_text(encoding="utf-8"))
                strategy = (pdata.get("portfolio", pdata)).get("strategy_template", "grid_value")
                # 触发进化评估
                auto_evolve(strategy, inv_dir.name, port_dir.name, workspace)
                # 触发规则学习
                from praxis.tools.adaptive import learn_rules
                learn_rules(workspace)
                return  # 只处理第一个投资者+组合
    except Exception:
        pass  # 触发失败不影响交易结果
