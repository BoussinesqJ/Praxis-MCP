"""重建 data/nav/default.jsonl 净值历史

问题：原文件混入种子垃圾（nav=1e6, total_assets=500000）。
口径：以权威收盘为基准，反推统一 baseline = AUTH_TA / AUTH_NAV，据此重算全部留存行，
      使整条 NAV 序列内部一致。
      历史行的 total_assets / positions_value / cash 等原快照值保留，仅重算 nav 字段；
      锚定日期行校正为权威收盘值。

注意：修改 AUTH_TA / AUTH_NAV 为实际值后运行。
"""
from __future__ import annotations
import json, shutil, sys, os

NAV_PATH = os.path.join(os.environ.get("PRAXIS_WORKSPACE", ""), "data", "nav", "default.jsonl")
AUTH_TA = 0.0              # 锚定日期权威总资产（运行前替换）
AUTH_NAV = 0.0              # 锚定日期权威 NAV（运行前替换）
BASELINE = (AUTH_TA / AUTH_NAV) if AUTH_NAV != 0 else 0

ANCHOR_DATE = "YYYY-MM-DD"  # 锚定日期（运行前替换）


def is_garbage(row: dict) -> bool:
    # 种子垃圾特征：nav 异常大 或 total_assets 为 500000 占位
    return float(row.get("nav", 0)) >= 100.0 or float(row.get("total_assets", 0)) >= 900000.0


def main():
    shutil.copy2(NAV_PATH, NAV_PATH + ".bak-0710")
    rows = []
    with open(NAV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    kept = [r for r in rows if not is_garbage(r)]
    print(f"原始 {len(rows)} 行 → 剔除垃圾 {len(rows)-len(kept)} 行 → 留存 {len(kept)} 行")

    out = []
    for r in kept:
        date = r["date"]
        if date == ANCHOR_DATE:
            # 校正为权威收盘值
            new = dict(r)
            new["total_assets"] = AUTH_TA
            new["nav"] = AUTH_NAV
            out.append(new)
            print(f"  {ANCHOR_DATE} 校正: nav→{AUTH_NAV}, total_assets→{AUTH_TA}")
        else:
            new = dict(r)
            new["nav"] = round(float(r["total_assets"]) / BASELINE, 4)
            out.append(new)

    out.sort(key=lambda x: x["date"])
    with open(NAV_PATH, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n基准 baseline = {BASELINE:.2f}")
    print("重建后序列（date / nav / total_assets）：")
    for r in out:
        print(f"  {r['date']}  nav={r['nav']:<8} ta={r['total_assets']}")

    # 一致性自检
    assert out[-1]["date"] == ANCHOR_DATE
    assert abs(out[-1]["nav"] - AUTH_NAV) < 1e-6
    assert all(0.5 < r["nav"] < 2.0 for r in out), "NAV 越界，重建异常"
    print("\nNAV REBUILD DONE ✅")


if __name__ == "__main__":
    main()
