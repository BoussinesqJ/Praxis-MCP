---
name: reconcile
version: 4.0.0
requires:
  praxis-mcp: ">=3.5"
  praxis_sdk: ">=1.0"
  rules_version: "v11"
description: 文档一致性校验 — 持仓数据一致性 + 规则编号连续性 + 三位一体隔离 + 元进化分析 + v3.5 工具整合
---

# reconcile

## 触发条件
- 用户说 `/reconcile`、"文档校验"
- 规则变更后自动触发
- 月度审计时自动触发

## 流程

```
Phase 1: 数据加载
├── 1.1 读取 project.md 持仓数据
├── 1.2 读取 finance_status_card.md
└── 1.3 读取 memory/long-term.md 规则定义

Phase 2: 交叉校验
├── 2.1 持仓数据一致性（project.md vs finance_status_card.md）
├── 2.2 规则编号连续性（Rule 1-10, Protocol 1-3, SOP 1-4）
├── 2.3 网格参数合理性（买点/止损/止盈逻辑）
├── 2.4 三位一体隔离合规（project.md 有价格, long-term.md 无价格）
├── 2.5 跨文件逻辑断裂检测（LCD）
├── 2.6 Skill 执行日志完整性（outputs/logs/）
└── 2.7 元进化数据分析（月度纪律代价趋势）

Phase 3: 输出校验报告
├── 3.1 列出所有矛盾项（若有）
├── 3.2 标注问题严重程度
└── 3.3 提供修复建议
```

## LCD 集成

```python
# 跨文件逻辑断裂检测
lcd_result = lcd_detector.check_portfolio_vs_rules(
    portfolio_state={"position_pct": position_pct, "tech_exposure_pct": tech_exposure},
    sentinel_bullish=sentinel_bullish
)

if not lcd_result.allowed:
    print("🚨 跨文件逻辑断裂：持仓状态违反当前规则")
    for conflict in lcd_result.conflicts:
        print(f"  - {conflict.message}")
```

## 输出模板

```markdown
# 📋 Praxis 文档一致性校验报告

## 一、持仓数据一致性
| 数据源 | 状态 | 说明 |
| project.md | ✅/❌ | 持仓数据是否最新 |
| finance_status_card.md | ✅/❌ | 是否与 project.md 一致 |

## 二、规则完整性
| 规则 | 状态 | 说明 |
| Rule 1-10 | ✅/❌ | 编号是否连续 |
| Protocol 1-3 | ✅/❌ | 是否完整 |
| SOP 1-4 | ✅/❌ | 是否定义 |

## 三、三位一体隔离
| 文件 | 状态 | 说明 |
| project.md | ✅/❌ | 是否包含具体价格/数量 |
| long-term.md | ✅/❌ | 是否包含具体价格/数量（应为否） |
| soul.md | ✅/❌ | 是否被修改（应为否） |

## 四、LCD 检测
- 组合层面违规：X 项
- 跨文件逻辑断裂：X 项

## 五、Skill 执行日志
- 最近执行记录：YYYY-MM-DD HH:MM
- 日志完整性：✅/❌

## 六、元进化分析
- 月度纪律代价趋势：[图表]
- 拦截收益比：X.XX
- 元进化建议：[建议]

## 校验结论
- 总体状态：✅ 正常 / ⚠️ 需关注 / ❌ 有矛盾
- 问题数量：X 项
- 修复建议：[建议]
```

## Error Handling

```
- 文件读取失败 → 标记 "⚠️ 文件不可达"，继续其他校验
- 数据解析失败 → 标记 "⚠️ 格式异常"，跳过该项校验
- LCD 检测失败 → 跳过 LCD 校验，不影响整体结论
```

## Cost Control

```
- token 上限: 4K
- 耗时预算: 20s
```

## 示例输出片段

```
## 一、持仓数据一致性
| 数据源 | 状态 | 说明 |
| project.md | ✅ | 最后更新: 2026-06-10 |
| finance_status_card.md | ✅ | 与 project.md 一致 |

## 三、三位一体隔离
| 文件 | 状态 | 说明 |
| project.md | ✅ | 包含具体价格/数量（正确） |
| long-term.md | ✅ | 仅包含定性描述（正确） |
| soul.md | ✅ | 未被修改（正确） |

## 四、LCD 检测
- 组合层面违规：0 项 ✅
- 跨文件逻辑断裂：0 项 ✅

## 校验结论
- 总体状态：✅ 正常
- 问题数量：0 项
```
