"""0710 账本迁移：去重(35->20) + 旧schema升级为运行代码的 Transaction 模型。

映射规则（全部可逆，原文件已备份）:
  type            -> tx_type          (字段改名)
  status:confirmed-> executed         (已确认成交=已执行)
  asset_type:fund -> offshore_fund    (OTC联接基金；受影响标的均已清仓net=0，对持仓无影响)
  null 可选字段    -> 模型默认值        (idempotency_key/decision_id/reason -> "")
去重: 按 tx_id 保留首次出现。
写入前用运行代码的 Transaction 模型逐条校验，确保 0 corrupt 才落盘。
"""
import sys, os, json, shutil, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from praxis.core.models import Transaction, AssetType, TransactionType, TransactionStatus

SRC = os.path.join(os.environ.get("PRAXIS_WORKSPACE", ""), "data", "ledger", "transactions.jsonl")
TMP = SRC + ".migrated.tmp"

ASSET_MAP = {"fund": "offshore_fund"}
STATUS_MAP = {"confirmed": "executed"}

def upgrade(d: dict) -> dict:
    o = dict(d)
    # type -> tx_type
    if "type" in o and "tx_type" not in o:
        o["tx_type"] = o.pop("type")
    # asset_type 映射
    at = o.get("asset_type")
    if at in ASSET_MAP:
        o["asset_type"] = ASSET_MAP[at]
    elif at is None:
        o.pop("asset_type", None)  # 用默认 STOCK
    # status 映射
    st = o.get("status")
    if st in STATUS_MAP:
        o["status"] = STATUS_MAP[st]
    elif st is None:
        o.pop("status", None)
    # null 可选字符串字段 -> 删除让默认生效
    for k in ("idempotency_key", "decision_id", "reason", "investor_id", "portfolio_id"):
        if o.get(k) is None:
            o.pop(k, None)
    return o

raw = [l for l in open(SRC, encoding="utf-8") if l.strip()]
seen, out, errors = set(), [], []
for i, line in enumerate(raw, 1):
    try:
        d = json.loads(line)
    except Exception as e:
        errors.append((i, "json", str(e))); continue
    txid = d.get("tx_id")
    if txid in seen:
        continue  # 去重
    seen.add(txid)
    up = upgrade(d)
    try:
        tx = Transaction(**up)  # 用运行模型校验
    except Exception as e:
        errors.append((i, txid, str(e)[:200])); continue
    out.append(tx.model_dump(mode="json"))

print(f"原始行数={len(raw)}  唯一tx_id={len(seen)}  迁移成功={len(out)}  失败={len(errors)}")
if errors:
    print("\n!! 存在失败记录，未落盘：")
    for e in errors[:20]:
        print("  ", e)
    sys.exit(1)

# 净持仓核对
from collections import defaultdict
net = defaultdict(float)
for t in out:
    q = float(t.get("quantity", 0) or 0)
    tt = t.get("tx_type")
    if tt in ("buy", "subscribe"): net[t["ticker"]] += q
    elif tt in ("sell", "redeem", "reverse"): net[t["ticker"]] -= q
print("\n净持仓:")
for tk, v in sorted(net.items()):
    flag = "  <== 持仓" if abs(v) > 1e-6 else ""
    print(f"  {tk}: {v:.2f}{flag}")

with open(TMP, "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"\n已写入临时文件: {TMP}")

# 用 FileLedger 复核临时文件
from praxis.core.ledger import FileLedger
lg = FileLedger(TMP)
print(f"FileLedger 复核: count={lg.count()}  list_len={len(lg.list(limit=1000))}")
if lg.count() != len(out):
    print("!! 复核不一致，未替换正式文件"); sys.exit(1)

# 备份 + 替换
bak = SRC + f".bak-migrate-{datetime.datetime.now():%Y%m%d%H%M%S}"
shutil.copy2(SRC, bak)
shutil.move(TMP, SRC)
print(f"备份原文件 -> {bak}")
print(f"已替换正式账本 -> {SRC}")
print("OK")
