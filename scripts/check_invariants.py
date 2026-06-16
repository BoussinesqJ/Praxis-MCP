#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动对账纠错与系统静态约束检查器（Invariants Linter）
"""
import os
import sys
import re

# 编码设置，确保在Windows环境下的正确输出
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 定义相关文件路径（支持环境变量覆盖）
_ws = os.environ.get("PRAXIS_WORKSPACE", ".")
PROJECT_PATH = os.path.join(_ws, os.environ.get("PRAXIS_PROJECT_PATH", "project.md"))
CARD_PATH = os.path.join(_ws, os.environ.get("PRAXIS_CARD_PATH", "finance_status_card.md"))
LONG_TERM_PATH = os.path.join(_ws, os.environ.get("PRAXIS_LONGTERM_PATH", "memory/long-term.md"))

def check_ticker_alignment():
    """
    断言 ①：标的一致性 (Ticker Alignment)
    在 project.md 中已标注为剔除的标的（如 513300），不应以活跃状态出现在 project.md 大表的挂单表或资金明细中。
    """
    errors = []
    # 基础黑名单
    blacklisted = ["513300"]
    
    if not os.path.exists(PROJECT_PATH):
        return [f"未找到 project.md: {PROJECT_PATH}"]
    with open(PROJECT_PATH, "r", encoding="utf-8") as f:
        project_content = f.read()
        
    if not os.path.exists(CARD_PATH):
        return [f"未找到 finance_status_card.md: {CARD_PATH}"]
    with open(CARD_PATH, "r", encoding="utf-8") as f:
        card_content = f.read()

    # 动态扫描 project.md 中的剔除关键字，扩充黑名单
    for line in project_content.split('\n'):
        if any(kw in line for kw in ["彻底剔除", "已剔除", "🚫"]):
            tickers = re.findall(r'\b(\d{6})\b', line)
            for t in tickers:
                if t not in blacklisted:
                    blacklisted.append(t)

    # 检查 project.md
    lines = project_content.split('\n')
    for idx, line in enumerate(lines, 1):
        for ticker in blacklisted:
            if ticker in line:
                if "彻底剔除" in line or "🚫" in line:
                    continue
                if f"v{ticker}" in line or "v4" in line or "v5" in line or "v8.5" in line or "v9.0" in line:
                    continue
                errors.append(f"project.md 第 {idx} 行包含已剔除标的 {ticker} 的活跃引用: {line.strip()}")
                
    # 检查 finance_status_card.md
    card_lines = card_content.split('\n')
    for idx, line in enumerate(card_lines, 1):
        for ticker in blacklisted:
            if ticker in line:
                if "彻底剔除" in line or "🚫" in line:
                    continue
                if "5/27" in line or "6/3" in line or "执行结果" in line:
                    continue
                errors.append(f"finance_status_card.md 第 {idx} 行包含已剔除标的 {ticker} 的活跃引用: {line.strip()}")
                
    return errors

def check_mathematical_balance():
    """
    断言 ②：账目守恒 (Mathematical Balance)
    1. 总资产 == 可用现金 + 持仓市值 (在 finance_status_card.md 里)
    2. 项目表中各项金额之和 == 总资产 (在 project.md 资金分布表中)
    3. 纯闲置现金 (未分配储备) 必须大于等于 0
    """
    errors = []
    if not os.path.exists(CARD_PATH):
        return [f"未找到 finance_status_card.md: {CARD_PATH}"]
    with open(CARD_PATH, "r", encoding="utf-8") as f:
        card_content = f.read()
        
    total_assets_match = re.search(r'- \*\*总资产\*\*：\s*([0-9,.]+)\s*CNY', card_content)
    cash_match = re.search(r'\*\s*可用现金[：:][\s\*\*]*([0-9,.]+)\s*元', card_content)
    
    if not total_assets_match or not cash_match:
        return ["finance_status_card.md 中解析总资产/可用现金失败"]
        
    total_assets = float(total_assets_match.group(1).replace(",", ""))
    available_cash = float(cash_match.group(1).replace(",", ""))
    
    # 提取持仓表格里的最新市值合计
    total_mv = None
    lines = card_content.split('\n')
    for line in lines:
        if line.strip().startswith('|') and "合计" in line:
            # 区分持仓表格合计与资金分布合计
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 6 and "合计" in parts[1]:
                mv_str = parts[5].replace("*", "").replace(",", "")
                try:
                    total_mv = float(mv_str)
                    break
                except ValueError:
                    continue
    
    if total_mv is None:
        return ["finance_status_card.md 中未找到持仓合计市值"]
    
    diff = abs(total_assets - (available_cash + total_mv))
    if diff > 0.05:
        errors.append(f"账目守恒断言失败(状态卡): 总资产({total_assets:,.2f}) != 可用现金({available_cash:,.2f}) + 持仓市值({total_mv:,.2f})，差额: {diff:.4f}元")

    if not os.path.exists(PROJECT_PATH):
        return errors
    with open(PROJECT_PATH, "r", encoding="utf-8") as f:
        project_content = f.read()
        
    start_tag = "<!-- FUNDS_DISTRIBUTION_START -->"
    end_tag = "<!-- FUNDS_DISTRIBUTION_END -->"
    if start_tag not in project_content or end_tag not in project_content:
        errors.append("project.md 中未找到 FUNDS_DISTRIBUTION 桩 (<!-- FUNDS_DISTRIBUTION_START/END -->)")
        return errors
        
    pattern = rf"{start_tag}([\s\S]*?){end_tag}"
    table_content = re.search(pattern, project_content).group(1)
    
    items_sum = 0.0
    declared_total = 0.0
    lines = table_content.strip().split('\n')
    for line in lines:
        if not line.strip().startswith('|') or '---' in line or '项目' in line:
            continue
        parts = [p.strip() for p in line.split('|')[1:-1]]
        if len(parts) >= 2:
            name = parts[0]
            val_str = re.sub(r'[^\d\.]', '', parts[1])
            if not val_str:
                continue
            val = float(val_str)
            if "合计" in name:
                declared_total = val
            else:
                items_sum += val
                
    diff_sum_declared = abs(items_sum - declared_total)
    if diff_sum_declared > 0.05:
        errors.append(f"账目守恒断言失败(资金分布表累加): 表中各项累加值({items_sum:,.2f}) != 表中标明合计({declared_total:,.2f})，差额: {diff_sum_declared:.4f}元")
        
    diff_assets = abs(declared_total - total_assets)
    if diff_assets > 0.05:
        errors.append(f"账目守恒断言失败(跨表总资产): 资金分布表合计({declared_total:,.2f}) != 状态卡总资产({total_assets:,.2f})，差额: {diff_assets:.4f}元")
        
    # 纯闲置现金穿仓校验
    idle_cash_match = re.search(r'纯闲置现金\s*\(未分配储备\)\s*\|\s*([0-9,\.-]+)\s*\|', project_content)
    if not idle_cash_match:
        errors.append("project.md 资金分布表中未找到【纯闲置现金 (未分配储备)】")
    else:
        idle_cash = float(idle_cash_match.group(1).replace(",", "").replace("-", "-"))
        if idle_cash < 0.0:
            errors.append(f"可用资金穿仓拦截：纯闲置现金为负数 ({idle_cash:,.2f} 元)！挂单及自选预算已套支可用现金总计！")
        
    return errors

def check_version_integrity():
    """
    断言 ③：版本闭环 (Version Integrity)
    读取 memory/long-term.md 进化记录的最新版本号，核对 project.md 头部版本是否一致。
    """
    errors = []
    if not os.path.exists(LONG_TERM_PATH):
        return [f"未找到 memory/long-term.md: {LONG_TERM_PATH}"]
    with open(LONG_TERM_PATH, "r", encoding="utf-8") as f:
        lt_content = f.read()
        
    lt_versions = re.findall(r'\|\s*(v[0-9\.]+)\s*\|', lt_content)
    if not lt_versions:
        errors.append("memory/long-term.md 中未找到版本号记录")
        return errors
    latest_lt_version = lt_versions[-1]
    
    if not os.path.exists(PROJECT_PATH):
        return [f"未找到 project.md: {PROJECT_PATH}"]
    with open(PROJECT_PATH, "r", encoding="utf-8") as f:
        proj_content = f.read()
        
    proj_version_match = re.search(r'最后更新：.*?\((v[0-9\.]+).*?\)', proj_content)
    if not proj_version_match:
        proj_version_match = re.search(r'## 💰 资产配置\（(v[0-9\.]+)', proj_content)
        
    if not proj_version_match:
        errors.append("project.md 中未找到版本号 (格式如 (v9.0 演进))")
        return errors
    proj_version = proj_version_match.group(1)
    
    if latest_lt_version != proj_version:
        errors.append(f"版本闭环断言失败: memory/long-term.md 最新版本为({latest_lt_version})，但 project.md 版本为({proj_version})")
        
    return errors

def check_risk_boundaries():
    """
    断言 ④：暴露度与风险边界断言 (Risk Exposure Border)
    科技股总暴露 ≤ 25%，可用现金储备比例 ≥ 40%。
    """
    errors = []
    if not os.path.exists(CARD_PATH):
        return [f"未找到 finance_status_card.md: {CARD_PATH}"]
    with open(CARD_PATH, "r", encoding="utf-8") as f:
        card_content = f.read()
        
    total_assets_match = re.search(r'- \*\*总资产\*\*：\s*([0-9,.]+)\s*CNY', card_content)
    cash_match = re.search(r'\*\s*可用现金[：:][\s\*\*]*([0-9,.]+)\s*元', card_content)
    if not total_assets_match or not cash_match:
        return ["finance_status_card.md 中解析总资产/可用现金失败"]
        
    total_assets = float(total_assets_match.group(1).replace(",", ""))
    available_cash = float(cash_match.group(1).replace(",", ""))
    
    cash_ratio = (available_cash / total_assets) * 100
    if cash_ratio < 40.0:
        errors.append(f"风险红线超标：可用现金储备占比为 {cash_ratio:.2f}%，低于防御红线 40.0%！")
        
    # 提取科技持仓市值
    lines = card_content.split('\n')
    in_holdings = False
    tech_mv = 0.0
    for line in lines:
        if "持仓明细" in line:
            in_holdings = True
            continue
        if in_holdings and line.startswith("|") and "合计" not in line and "标的" not in line and "---" not in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 6:
                ticker_full = parts[1]
                is_tech = False
                for tech_kw in ["000001", "512480", "510050", "示例基金", "半导体", "示例科创"]:
                    if tech_kw in ticker_full:
                        is_tech = True
                        break
                if is_tech:
                    mv_str = re.sub(r'[^\d\.]', '', parts[5])
                    if mv_str:
                        tech_mv += float(mv_str)
        elif in_holdings and "合计" in line:
            in_holdings = False
            
    tech_ratio = (tech_mv / total_assets) * 100
    if tech_ratio > 25.0:
        errors.append(f"风险红线超标：泛科技板块暴露比例为 {tech_ratio:.2f}%，已突破风控上限 25.0%！")
        
    return errors

def run_linter():
    print("====== 🔍 启动系统静态约束检查器 (Invariants Linter) ======")
    all_errors = []
    
    print("[*] 检查断言 ①: 标的一致性 (Ticker Alignment)...")
    ticker_errors = check_ticker_alignment()
    if ticker_errors:
        print("  [-] 失败！发现标的一致性冲突：")
        for e in ticker_errors:
            print(f"    - {e}")
        all_errors.extend(ticker_errors)
    else:
        print("  [OK] 标的一致性通过。")
        
    print("[*] 检查断言 ②: 账目守恒 (Mathematical Balance)...")
    math_errors = check_mathematical_balance()
    if math_errors:
        print("  [-] 失败！发现账目差额或表结构不符：")
        for e in math_errors:
            print(f"    - {e}")
        all_errors.extend(math_errors)
    else:
        print("  [OK] 账目守恒通过。")
        
    print("[*] 检查断言 ③: 版本闭环 (Version Integrity)...")
    version_errors = check_version_integrity()
    if version_errors:
        print("  [-] 失败！发现版本不一致：")
        for e in version_errors:
            print(f"    - {e}")
        all_errors.extend(version_errors)
    else:
        print("  [OK] 版本闭环通过。")
        
    print("[*] 检查断言 ④: 暴露度与风险边界 (Risk Exposure Border)...")
    risk_errors = check_risk_boundaries()
    if risk_errors:
        print("  [-] 失败！突破配置红线限制：")
        for e in risk_errors:
            print(f"    - {e}")
        all_errors.extend(risk_errors)
    else:
        print("  [OK] 暴露度与风险边界校验通过。")
        
    print("=========================================================")
    if all_errors:
        print(f"\033[91m[-] 检查失败！共发现 {len(all_errors)} 个静态约束冲突！请根据上述报错信息进行数据修正。\033[0m")
        return False
    else:
        print("\033[92m[+] 检查成功！所有静态约束断言全部通过，系统数据无冲突。\033[0m")
        return True

if __name__ == "__main__":
    success = run_linter()
    sys.exit(0 if success else 1)
