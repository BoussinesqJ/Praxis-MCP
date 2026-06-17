---
name: quick-check
version: 4.1.0
requires:
  praxis-mcp: ">=3.5"
  praxis_sdk: ">=1.0"
  rules_version: "v11"
description: 秒级资产/哨兵核检，含引力热力图 + v4.1.0 门闸同步
---

# quick-check

## 触发条件
- 用户说 `/quick`、"快速看一下"、"行情"

## 🔴 成本价唯一源 (CRITICAL)
quick-check 输出中涉及的成本价，必须与 `project.md` 持仓表的「成本」列一致。
`portfolio_tool` / `nav_tool` 返回的工具成本值仅做交叉参考，不可直接输出为"持仓成本"。

## 执行流程

**直接运行 Python 脚本，禁止 Agent 二次翻译。**

```bash
cd /path/to/praxis
python praxis_sdk/scripts/quick_check.py
```

脚本会自动：
1. 调用数据源管理器（三级优先级：mx-data → akshare → 东方财富直连）
2. 读取缓存（60秒 TTL）
3. 计算 LCD 检测
4. 生成引力热力图
5. 输出最终白话摘要

## 输出要求

**直接透传 Python 输出，禁止修改。**

**如果 Python 已经输出了引力图，Agent 严禁重新分析一遍。**

Agent 仅负责对 Python 输出的 LCD 冲突进行一句话总结：
- 如果 LCD 检测到冲突 → 补充一句解释
- 如果 LCD 无冲突 → 不补充

## 数据源优先级

系统按以下顺序尝试获取行情，任何一级成功后立即返回并缓存：

1. **Tier 1: mx-data** - 原生平台集成，绕过所有本地代理干扰
2. **Tier 2: akshare** - 利用本地计算能力，适合多标的并行拉取
3. **Tier 3: 东方财富直连** - 最后的回退方案

缓存位置：`outputs/logs/price_cache.json`

## Error Handling

```
- 脚本执行失败 → 显示错误信息，不编造数据
- 缓存过期 → 自动刷新
- 所有数据源失败 → 显示"数据获取失败"
```

## Cost Control

```
- token 上限: 1K（仅透传输出）
- 耗时预算: 2秒
```
