---
name: three-team
version: 4.1.0
requires:
  praxis-mcp: ">=3.5"
  praxis_sdk: ">=1.0"
  rules_version: "v11"
description: 三团队联合研判 — ASRG战术 + Masters哲学 + Trading执行，含 Context Seeding + Consensus Check + 逻辑对撞室 + v3.5 工具整合
---

# three-team

## 触发条件
- 用户说 `/analyze`、"三团队分析"、"启动研判"
- 自动触发条件（任一满足）：
  1. 止损触发或距止损<10%
  2. 大盘单日跌>3%
  3. 持仓单只亏>5%
  4. 新标的进入观察池
  5. 规则变更后验证
  6. 用户显式要求

## 流程

### 🔴 严禁并发调用规则 (CRITICAL)
底层 MCP 数据通道不支持高并发。在 Phase 1 (数据准备) 阶段，你必须**严格串行**调用工具。
即：调用第一个工具 -> 等待返回结果 -> 才能调用第二个工具。
绝对禁止使用并行工具调用（Parallel Tool Calling）一次性发送多个请求，否则将导致管道死锁崩溃。

## 🔴 子Agent调用凭证 (CRITICAL)
Phase 2-4 中每个子 Agent 调用 `task()` 时必须记录 `call_timestamp`。
```
Phase 5 汇编时，汇总表必须列出每个子Agent的：
  - agent_id（如 ethan, james, kevin, oracle-of-omaha 等）
  - call_timestamp（ISO 8601 格式）
  - 状态（completed / timeout / skipped）
```
无调用时间戳的三团队结论 = 脑补，不予采纳，整份报告作废。

```
Phase 0: Context Seeding（同步原语）
└── 0.1 将最新 project.md 数据注入所有子 Agent prompt

Phase 1: 数据准备（~2K tokens, 严格串行）
├── 1.1 收集所有持仓+观察池数据 [等待返回]
├── 1.2 调用 news_tool 获取新闻 [等待返回]
├── 1.3 调用 sentiment_tool 情绪分析 [等待返回]
├── 1.4 调用 research_report_tool 获取研报 [等待返回]
└── 1.5 组装数据包

Phase 2: ASRG 战术研究（task子Agent，~16K tokens）
├── 2.1 Ethan: 个股诊断
├── 2.2 James: 估值判定
├── 2.3 Kevin: 资金信号
└── 2.4 Gavin: 汇编输出 → deliverables/a-share/

Phase 3: Masters 大师圆桌（task子Agent，~12K tokens）
├── 3.1 巴菲特: 价值视角
├── 3.2 成长学派: 成长视角
├── 3.3 风险管理师: 风控视角
└── 3.4 Arthur: 汇编输出 → deliverables/investment-masters/

Phase 4: Trading 交易执行（task子Agent，~32K tokens）
├── 4.1 数据收集 4 人并行
├── 4.2 多空辩论 3 人顺序
├── 4.3 交易员出方案
├── 4.4 风险评估 3 人并行
└── 4.5 Dominic: 最终裁决 → outputs/trading_team/

Phase 5: 联合输出 + Consensus Check（~6K tokens）
├── 5.1 等待3个task完成（wait）
├── 5.2 汇编三团队结论
├── 5.3 Consensus Check:
│     ├── ASRG 是否标注 [Logic_Strong_Validation]？
│     ├── Trading 是否计算出有效 PDA？
│     └── 两者结论相左 → 插入 "⚖️ 逻辑对撞室"
├── 5.4 逻辑对撞室（若触发）：
│     ├── 列出 ASRG vs Trading 的分歧点
│     ├── 调用 LCD 仲裁模式
│     └── Masters 做最终裁决（价值底线优先）
├── 5.5 生成联合报告 → deliverables/a-share/YYYY-MM-DD-联合研判.md
└── 5.6 对话中输出精简总结

Phase 6: 审计日志
└── 6.1 写入 outputs/logs/skill-execution.jsonl
```

## 子Agent执行方式

```python
# Phase 2-4 使用 task() 工具并行执行
asrg_task = task(
    prompt=open('.reasonix/skills/three-team/templates/asrg.md').read(),
    run_in_background=True
)
masters_task = task(
    prompt=open('.reasonix/skills/three-team/templates/masters.md').read(),
    run_in_background=True
)
trading_task = task(
    prompt=open('.reasonix/skills/three-team/templates/trading.md').read(),
    run_in_background=True
)

# Phase 5 等待完成
wait(job_ids=[asrg_task, masters_task, trading_task])
```

## MCP 工具调用

```python
# Phase 1: 数据准备
sentinel_tool(action="scan")
get_portfolio_summary_tool(investor="demo", portfolio="core")
news_tool(action="finance", sources=["cls", "wallstreetcn"])
sentiment_tool(action="batch", texts=[新闻标题列表])

# Phase 1: 新增数据源（v3.1）
research_report_tool(action="eps", ticker="000001")  # 持仓股一致预期 EPS
research_report_tool(action="list", ticker="000001", limit=5)  # 最新研报

# Phase 5: LCD 仲裁
# 调用 lcd_detector.consensus_check(asrg_output, trading_output)
```

## LCD 集成

### Consensus Check
检查 ASRG 和 Trading 团队结论是否一致：
```python
lcd_result = lcd_detector.consensus_check(
    asrg_output={"logic_strong_validation": True, "recommendation": "buy"},
    trading_output={"pda_valid": False, "recommendation": "sell"}
)

if not lcd_result.allowed:
    # 插入逻辑对撞室
    print("⚖️ 逻辑对撞室：ASRG 与 Trading 结论相左")
    print("Masters 做最终裁决（价值底线优先）")
```

## 降级策略

```
Level 1: 三团队全开（默认）
Level 2: 仅 ASRG + Trading（省 ~35% token）
Level 3: 仅 ASRG（省 ~75% token）

自动降级条件：
- 距上次 three-team 执行 < 4小时 → Level 2
- 今日已触发过 three-team → Level 3
- token 预算剩余 < 30K → Level 2
- token 预算剩余 < 15K → Level 3
```

## Error Handling

```
- 单个子Agent超时 → 标记 "X团队本次未参与"，其余继续
- 两个子Agent都失败 → 仅输出幸存团队结论
- 三个子Agent都失败 → 输出 "三团队本次均未完成" + 原始数据
- Phase 5 汇编失败 → 分别输出三份独立报告
- 原则：输出可不完整，绝不伪造
```

## Cost Control

```
- token 上限: 80K（硬限制）
- 单个子Agent token 上限: 15K
- 子Agent 默认模型: DeepSeek Flash（reasonix.toml 已配置）
- 每日最多触发: 1次
- 成本估算: DeepSeek ~¥X/次 | Claude Sonnet ~¥X/次
```

## 输出模板（精简通俗版）

```markdown
<!-- Skill: three-team v1.1 | 执行: YYYY-MM-DD HH:MM | 耗时: Xs -->
# 📊 三团队联合研判报告 - YYYY-MM-DD (精简通俗版)

## 核心结论 (TL;DR)
- **大盘环境**：[一句话概括当前系统环境与估值]
- **仓位风险**：[说明当前仓位与纪律红线的距离]
- **操作指令**：[明确的买/卖/持有指令，说明原因]

---

## 一、ASRG 战术层 (宏观与基本面)
- **Ethan (个股)**：[大白话诊断结论]。建议：[多/空/平]
- **James (估值)**：[大白话估值评价]。建议：[多/空/平]
- **Kevin (资金)**：[大白话资金与情绪动向]。建议：[多/空/平]
- **团队共识**：[一句话总结ASRG共识]

## 二、Masters 哲学层 (投资原则)
- **巴菲特 (价值)**：[安全边际与价值底线评价]
- **成长学派 (趋势)**：[成长性与周期评价]
- **风险管理师 (风控)**：[纪律与本金安全警告]
- **团队共识**：[一句话总结Masters共识]

## 三、Trading 执行层 (交易与风控)
- **多空辩论**：[买方与卖方的核心冲突点，如网格 vs 仓位红线]
- **风险评估**：[PDA动能与LCD对撞情况的通俗解释]
- **最终裁决 (Dominic)**：[最终执行指令：如 撤单 / 买入 / 观望]

---

## 四、最终操作建议
| 标的 | 建议操作 | 执行说明 |
|:---|:---|:---|
| [标的1] | **[具体动作]** | [大白话说明] |
| [标的2] | **[具体动作]** | [大白话说明] |
| [闲置现金] | **[持币/买理财]** | [大白话说明] |

### 🛡️ 本次研判逻辑快照
- **Consensus Check**: ASRG 与 Trading [完全一致 / 严重分歧]
- **LCD 仲裁**: [未触发 / 已强制干预]
- **降级状态**: [Level 1 物理隔离 / Level 3 单进程脑补]
```

## 示例输出片段

```
## 四、Consensus Check
- ASRG 标注: [Logic_Strong_Validation] ✅
- Trading PDA: 无效 ⚠️
- 结论状态: ⚖️ 相左 → 触发逻辑对撞室

## 五、逻辑对撞室
**分歧点**：
- ASRG 认为中天科技 Q1 业绩拐点，建议积极买入
- Trading 认为大盘趋势向下，PDA 无效，建议观望

**LCD 仲裁**：
Rule 2 仓位红线优先（当前持仓 10.1%），即使 ASRG 强验证，也不宜在绝对防守期加仓。

**Masters 最终裁决**：
等待仓位回落至 8% 以下 + 哨兵回暖至 3 个以上，再考虑 ASRG 的买入建议。

## 六、联合结论
一句话：三团队研判结论为"等待"，当前不宜加仓，等 Rule 2 红线解除后再行动。
```
