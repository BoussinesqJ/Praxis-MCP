"""0710 哨兵历史对齐：消除 07-10 的 Rule23 漂移。
保留与已交付复盘/状态卡一致的 canonical 条目(consecutive_days=6, bullish=1)，
移除两条 new-format 漂移条目(consecutive_days=0, bullish=0, 更换了哨兵成分)。
原文件备份。"""
import json, shutil, datetime, os
SRC = os.path.join(os.environ.get("PRAXIS_WORKSPACE", ""), "data", "sentinel_history.jsonl")
lines = [l for l in open(SRC, encoding="utf-8") if l.strip()]
recs = [json.loads(l) for l in lines]
print(f"原始条目={len(recs)}")

out = []
dropped = []
for r in recs:
    if r.get("date") == "2026-07-10" and r.get("rule23_consecutive_days") == 0:
        dropped.append(r); continue  # 漂移条目
    out.append(r)

# 校验：07-10 应只剩 1 条 canonical
d0710 = [r for r in out if r.get("date") == "2026-07-10"]
print(f"保留条目={len(out)}  丢弃漂移={len(dropped)}")
print(f"07-10 剩余={len(d0710)} 条 -> consecutive_days="
      f"{[r['rule23_consecutive_days'] for r in d0710]}, "
      f"bullish={[r['bullish_count'] for r in d0710]}, "
      f"rule23={[r['rule23_triggered'] for r in d0710]}")
assert len(d0710) == 1 and d0710[0]["rule23_consecutive_days"] == 6, "canonical 校验失败"

bak = SRC + f".bak-align-{datetime.datetime.now():%Y%m%d%H%M%S}"
shutil.copy2(SRC, bak)
with open(SRC, "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"备份 -> {bak}")
print(f"已写回 -> {SRC}")
print("OK")
