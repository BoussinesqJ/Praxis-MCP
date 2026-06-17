---
name: daily-review
version: 4.2.0
requires:
  praxis-mcp: ">=3.5"
  rules_version: "v11"
description: 日终复盘 — 物理对账 + 三团队联合研判 + 状态卡联动 + 纪律代价统计
---

# daily-review

## 触发条件
- 用户说 `/daily-review`、"做日终复盘"、"今日复盘"
- A股收盘后自动触发

## 🔴 严禁并发调用规则 (CRITICAL)
底层 MCP 数据通道不支持高并发。必须**严格串行**调用工具。
绝对禁止使用并行工具调用（Parallel Tool Calling），否则将导致管道死锁崩溃。

## 🔴 交易前账实核对死线 (CRITICAL)
在复盘结论中，若带有任何买卖调仓倾向，必须在输出内容首部加粗声明：**系统已触发【强制对账】纪律，请主理人确认底层账本与券商实盘资金一致。**

## 🔴 写入纪律 (CRITICAL)
任何写回状态卡的操作，必须在对话中先展示 diff 内容（旧值 → 新值），经主理人确认后才能写入。

## 🔴 成本价唯一源 (CRITICAL)
复盘报告中所有标的的**成本价**必须从 `project.md` 持仓表的「成本」列读取。
`portfolio_tool` / `nav_tool` 返回的成本仅做交叉参考（标注"工具参考值"），不可直接写入报告。
若两者偏差 >2%，应抛异常并提示手工核对。

## 🔴 持仓全量校验 Gate (CRITICAL)
Phase 1 完成后、Phase 2 开始前，强制执行：
```
Step 1: 从 project.md 读取持仓标的列表 → expected_set
Step 2: 从 portfolio_tool 返回的持仓数据提取标的列表 → actual_set
Step 3: 比对 expected_set == actual_set？
        否 → 列出 missing = expected_set - actual_set
             列出 extra  = actual_set - expected_set
             打印"⚠️ 持仓数量不匹配，回退 Phase 1 补采数据"
             回退 Phase 1 重新采集
        是 → ✅ 通过，进入 Phase 2
```
最低成本的防漏兜底——一行集合比对即可。

## 🔴 状态卡联锁更新 (CRITICAL)
Phase 6 中「更新 finance_status_card.md」为**强制非可选**步骤：
```
复盘报告落盘 outputs/ → 检测 finance_status_card.md 时间戳 →
若时间戳 < 今日 → 强制展示 diff（旧值→新值清单）→ 主理人确认 → 同步写入
```
不强制执行的后果就是复盘与状态卡两张皮。

## 🔴 持仓双向同步 (CRITICAL)
`project.md`（前端 SSOT）与 `investors/<id>/portfolios/<id>/portfolio.yaml`（后端引擎配置）必须始终保持一致。

每次复盘 Phase 1「📖 READ」阶段，比对两边的持仓标的列表：

```
Step 1: 从 project.md 读取持仓标的列表 → md_set
Step 2: 从 portfolio.yaml 读取 assets[].ticker → yaml_set
Step 3: md_set == yaml_set？
        否 → missing_in_yaml = md_set - yaml_set
              extra_in_yaml = yaml_set - md_set
              若有 missing_in_yaml → 自动追加到 portfolio.yaml 的 assets 列表
              若有 extra_in_yaml    → 标记人工确认（可能是废弃标的）
              打印"⚠️ 持仓配置不同步，已自动修复" 或 "⚠️ 请人工确认 extra 标的"
              阻塞 Phase 1 继续，直到同步完成
        是 → ✅ 通过，进入 1.1
```

前店（project.md）后厂（portfolio.yaml）分离的代价就是这次 510050 消失的根源。

## 🔴 净值强制入库 (CRITICAL)
日终复盘的最后一环（Phase 6 末尾、Phase 7 之前）必须调用 `nav_tool(action="record")` 将当日净值快照写入底层 NAV Ledger。

```
执行顺序：
  6.5 nav_tool(action="record", investor, portfolio) → 【强制】记录净值
       └── 调用成功 → 审计日志写入 nav_recorded: true
       └── 调用失败或跳过 → 审计日志写入 nav_recorded: false，报告标记为 "⚠️ 未交卷"
```

净值只写在 finance_status_card.md 而 NAV Ledger 断档 = 系统底层缺少历史净值序列，绩效计算/回测全部失准。

---

## 流程

```
Phase 1: 数据采集（严格串行，每个工具单独调用）
│
│  📖 READ: project.md → 持仓标的列表 + 成本 + 网格档位 + 止损位
│           finance_status_card.md → 可用资金 + 资产配比 + 上次净值
│           investors/<id>/portfolios/<id>/portfolio.yaml → assets 列表
│
│  ┌── 🔴 持仓双向同步 Checkpoint（比对 project.md vs portfolio.yaml）
│  │    通过 → 进入 1.1
│  │    不通过 → 自动补齐 portfolio.yaml / 标记人工确认 → 阻塞直到同步完成
│  │
├── 1.1 reconcile_tool(investor, portfolio) → 【强制】物理对账 [等待返回]
├── 1.2 sentinel_tool(action="scan") → 哨兵扫描 [等待返回]
├── 1.3 valuation_tool(action="all") → 估值分位 [等待返回]
├── 1.4 market_data_ext_tool(action="northbound", days=5) → 北向资金 [等待返回]
├── 1.5 market_data_ext_tool(action="fund_flow", ticker="000001") → 资金流向 [等待返回]
├── 1.6 get_performance_tool(investor, portfolio) → 绩效指标 [等待返回]
├── 1.7 portfolio_tool(action="summary", investor, portfolio) → 持仓概览 [等待返回]
├── 1.8 benchmark_tool(action="data", index_code="000300") → 大盘数据 [等待返回]
├── 1.9 news_tool(action="finance", sources=["cls", "wallstreetcn"]) → 财经新闻 [等待返回]
└── 1.10 sentiment_tool(action="analyze", text=<新闻标题>) → 消息面情感 [等待返回]

    ┌── 🔴 Gate Check: 持仓全量校验（比对 project.md vs portfolio_tool 标的集合）
    │    通过 → 进入 Phase 2  不通过 → 打印缺失列表，回退 Phase 1
    │
    └── 📋 Phase 1 数据快照（结构化输出，供Phase2-6使用）:
        {
          "哨兵": "X/8 多/空",
          "持仓标的": ["ticker1","ticker2",...],
          "今日新增": ["ticker"],         // reconcile 比对出的今日新建仓标的
          "各标现价": {"ticker": price},
          "总市值": number,
          "现金": number,
          "总资产": number,
          "总浮盈": number,
          "project.md标的数": expected_count,
          "实际标的数": actual_count,
          "对账结果": "✅ 吻合 / ⚠️ 偏差见missing列表"
        }

Phase 2: 规则审计（纯计算 + LCD + 回归测试）
├── 2.1 逐条检查 Rule 1-10 合规
│       └── Rule 6 科技暴露：计入所有科技/科创类标的（000002 + 510050 等）
├── 2.2 检查 Protocol 1-3 状态
├── 2.3 计算攻防状态（哨兵多头数 → 仓位上限）
├── 2.4 检查 Rule 5 估值拦截/预警
├── 2.5 LCD 检测：挂单 vs 仓位红线对撞
├── 2.6 回归测试标记：运行 rule_scenarios.json 验证
└── 2.7 ⚠️ 资金流向预警：检查持仓股主力资金异常净流出

Phase 3: 纪律代价统计
├── 3.1 统计本月因拦截错失的收益
├── 3.2 统计本月因拦截规避的风险
└── 3.3 计算拦截收益比，判断是否需要元进化建议

Phase 4: 引力热力图
└── 4.1 对每只持仓标的生成 MA10/MA20/MA30 引力带

Phase 5: 三团队分析（✅ 每日复盘必含，不可跳过）
├── 5.1 检查 Phase 1 数据快照的「今日新增」列表
│       └── 若有今日新增持仓 → 将其设为三团队第一个分析对象（C位）
│           报告中标 🔴 新仓首日审查 标识
│           ASRG 评产业逻辑 / Masters 评沙盒风险敞口 / Trading 评 MA10 动态止损距离
├── 5.2 ⚠️ 每次日终复盘必须执行三团队分析，无条件触发
├── 5.3 调用 three-team skill（ASRG + Masters + Trading）
│       └── 🔴 **每个子成员必须逐一调用 member_prompt 生成分析，不得跳过或取巧用 compile_prompt 替代**
│       └── 🔴 **每个子成员调用时必须记录 call_timestamp，汇总表必须列出每个成员的 member_id + call_timestamp**
│           无调用时间戳的三团队结论 = 脑补，不予采纳，整份三团队报告作废
├── 5.4 编译各子成员分析 → 生成三团队联合研判报告
└── 5.5 生成三团队联合研判报告 → outputs/YYYY-MM-DD-three-team-analysis.md

Phase 6: 输出生成（状态卡联锁更新为强制步骤）
│  ✍️ WRITE: project.md → 更新持仓状态/条件单/止损价（需主理人确认）
│            finance_status_card.md → **强制**更新净值/收益率/资产配比/执行矩阵（需主理人确认）
│            long-term.md → 若有规则变更，追加归因审计记录（执行 5 日滚动归档）
│
├── 6.1 生成复盘报告 → outputs/YYYY-MM-DD-daily-review.md
├── 6.2 更新 project.md 持仓状态（需主理人确认）
├── 6.3 🔴 强制更新 finance_status_card.md
│       └── 检测状态卡时间戳 < 今日 → 打印 diff（旧净值→新净值/旧资产→新资产）→ 主理人确认 → 写入
├── 6.4 对话中输出精简总结
│
├── 6.5 🔴 nav_tool(action="record", investor, portfolio) → 【强制】记录当日净值快照
│       └── 成功 → 继续 Phase 7
│       └── 失败 → 审计日志标记 nav_recorded: false，报告标记 ⚠️ 未交卷
│
└── 进入 Phase 7

Phase 7: 审计日志
└── 7.1 写入 outputs/logs/skill-execution.jsonl
```

## Phase 1 数据快照（关键中间产物）

Phase 1 完成后、Gate Check 通过后，必须输出以下结构化数据再进入 Phase 2：

```json
{
  "哨兵": "5/8 多头",
  "持仓标的": ["600000","000001","000002","510050"],
  "今日新增": ["510050"],
  "各标现价": {"600000":0.00, "000001":0.00, "510050":0.00, "000002":0.00},
  "总市值": 0,
  "现金": 0,
  "总资产": 0,
  "总浮盈": 0,
  "project.md标的数": 0,
  "实际标的数": 4,
  "对账结果": "✅ 吻合"
}
```

Planner/Executor 用此快照做完整性校验，再放行 Phase 2。比事后修报告代价小得多。

## MCP 工具调用

```python
# Phase 1: 数据采集（严格串行，每个工具单独调用）
reconcile_tool(investor="demo", portfolio="core")           # 【强制】物理对账
sentinel_tool(action="scan")                                       # 哨兵扫描
valuation_tool(action="all")                                       # 估值分位
market_data_ext_tool(action="northbound", days=5)                  # 北向资金
market_data_ext_tool(action="fund_flow", ticker="000001")          # 资金流向
get_performance_tool(investor="demo", portfolio="core")     # 绩效指标
portfolio_tool(action="summary", investor="demo", portfolio="core")  # 持仓概览
benchmark_tool(action="data", index_code="000300")                 # 大盘数据
news_tool(action="finance", sources=["cls", "wallstreetcn"])       # 财经新闻
sentiment_tool(action="analyze", text="<新闻标题>")                # 消息面情感
```

## LCD 集成

```bash
python praxis_sdk/cli.py lcd --check portfolio
python praxis_sdk/tests/test_scenarios.py
python praxis_sdk/visualization/gravity_renderer.py --ticker <代码> --price <价格> --ma10 <MA10> --ma20 <MA20> --ma30 <MA30>
```

## Error Handling
- Phase 1 任一工具失败 → 重试1次 → 仍失败标记 "⚠️数据缺失"，继续后续Phase
- Phase 5 三团队中单个子Agent超时 → 标记 "X团队本次未参与"，其余继续
- Phase 6.5 nav_tool 失败 → 审计日志标记 nav_recorded: false，报告标记 ⚠️ 未交卷
- 写文件失败 → 降级为对话输出
- 原则：输出可不完整，绝不伪造
- **Gate Check 失败** → 必须回退 Phase 1 补采，不可跳过

## Cost Control
- token 上限: 8K（不含三团队）
- 三团队触发时: 额外 +68K
- 每日总预算: ¥XX（超过则降级为不含三团队）
- three-team 每日最多触发1次，间隔 ≥ 4小时

## 三团队触发条件
1. ✅ **每日复盘**（默认包含，无条件触发）
2. ✅ **每日策略报告**（默认包含，无条件触发）
3. **止损触发或距止损<10%**
4. **大盘单日跌>3%**
5. **持仓单只亏>5%**
6. **新标的进入观察池**
7. **规则变更后验证**
8. **用户显式要求**

⚠️ **铁律**：日终复盘 = 三团队分析，不可跳过。
