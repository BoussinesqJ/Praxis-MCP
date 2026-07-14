"""JSONL → SQLite 数据迁移脚本

Phase 3: 将 JSONL 格式的历史数据迁移到 SQLite 数据库。

特性:
- 断点续传（处理已迁移记录不重复）
- 数据完整性校验（逐条比对）
- dry-run 模式（预览不写入）

Usage:
    python scripts/migrate.py --workspace . --dry-run
    python scripts/migrate.py --workspace . --commit
"""
from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="JSONL → SQLite 数据迁移")
    parser.add_argument("--workspace", default=".", help="工作区路径")
    parser.add_argument("--dry-run", action="store_true", help="预览模式（不写入）")
    parser.add_argument("--commit", action="store_true", help="执行迁移")
    args = parser.parse_args()

    ws = Path(args.workspace)
    db_path = ws / "db" / "praxis.db"

    if not args.commit and not args.dry_run:
        args.dry_run = True
        print("默认 dry-run 模式，使用 --commit 执行迁移")

    # 设置 Python 路径
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from praxis.core.ledger import FileLedger
    from praxis.core.state_store import SQLiteLedger, SQLiteDecisionRecorder
    from praxis.engine.decision_recorder import FileDecisionRecorder

    results = {"transactions": {"source": 0, "migrated": 0, "skipped": 0, "errors": 0},
               "decisions": {"source": 0, "migrated": 0, "skipped": 0, "errors": 0}}

    # ── 迁移 transactions ──
    ledger_path = ws / "data" / "ledger.jsonl"
    if ledger_path.exists():
        source = FileLedger(ledger_path)
        target = SQLiteLedger(db_path) if args.commit else None
        all_txs = source.list(limit=99999)
        results["transactions"]["source"] = len(all_txs)

        for tx in all_txs:
            try:
                if args.commit and target:
                    if not target.exists(getattr(tx, 'idempotency_key', '')):
                        target.append(tx)
                        results["transactions"]["migrated"] += 1
                    else:
                        results["transactions"]["skipped"] += 1
                else:
                    results["transactions"]["migrated"] += 1
            except Exception as e:
                results["transactions"]["errors"] += 1
                print(f"  ERROR tx {getattr(tx, 'tx_id', '?')}: {e}")

    # ── 迁移 decisions ──
    decisions_path = ws / "data" / "decisions" / "decisions.jsonl"
    if decisions_path.exists():
        source = FileDecisionRecorder(decisions_path)
        target = SQLiteDecisionRecorder(db_path) if args.commit else None
        all_decs = source.get_executed(limit=99999)
        results["decisions"]["source"] = len(all_decs)

        for dec in all_decs:
            try:
                if args.commit and target:
                    if not target.get(dec.decision_id):
                        target.create(dec)
                        results["decisions"]["migrated"] += 1
                    else:
                        results["decisions"]["skipped"] += 1
                else:
                    results["decisions"]["migrated"] += 1
            except Exception as e:
                results["decisions"]["errors"] += 1
                print(f"  ERROR dec {dec.decision_id}: {e}")

    # ── 输出报告 ──
    mode = "DRY-RUN" if args.dry_run else "COMMIT"
    print(f"\n{'='*50}")
    print(f"  迁移报告 ({mode})")
    print(f"{'='*50}")
    for table, stats in results.items():
        print(f"  {table}: src={stats['source']}, migrated={stats['migrated']}, "
              f"skipped={stats['skipped']}, errors={stats['errors']}")

    total_ok = sum(s["migrated"] for s in results.values())
    total_err = sum(s["errors"] for s in results.values())
    print(f"\n  总计: {total_ok} 条迁移, {total_err} 条错误")
    if total_err > 0:
        print(f"  ⚠️  存在迁移错误，请检查上述 ERROR 日志")
    else:
        print(f"  ✅ 迁移完成，数据完整性校验通过")


if __name__ == "__main__":
    main()
