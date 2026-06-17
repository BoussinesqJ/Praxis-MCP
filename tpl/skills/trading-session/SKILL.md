---
name: trading-session
version: 4.2.0
requires:
  praxis-mcp: ">=3.5"
  rules_version: "v11"
description: 盘前策略 — PDA 动态测算 + 交易矩阵 + LCD 冲突检测 + 状态卡联动
---

# trading-session

## 触发条件
- 用户说 `/trading`、"明日策略"、"盘前策略"
- A股开盘前或收盘后生成次日策略时

## 🔴 严禁并发调用规则 (CRITICAL)
底层 MCP 数据通道不支持高并发。必须**严格串行**调用工具。
绝对禁止使用并行工具调用（Parallel Tool Calling），否则将导致管道死锁崩溃。

## 🔴 交易前账实核对死线 (CRITICAL)
在策略输出中，若带有任何买卖调仓倾向，必须在输出内容首部加粗声明：**系统已触发【强制对账】纪律，请主理人确认底层账本与券商实盘资金一致。**

## 🔴 写入纪律 (CRITICAL)
任何写回状态卡的操作，必须在对话中先展示 diff 内容（旧值 → 新值），经主理人确认后才能写入。

## 🔴 成本价唯一源 (CRITICAL)
策略报告中所有标的的**成本价**必须从 `project.md` 持仓表的「成本」列读取。
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

## 🔴 状态卡联锁更新 (CRITICAL)
Phase 3 中「更新 finance_status_card.md」为**强制非可选**步骤：
```
策略报告落盘 outputs/ → 检测 finance_status_card.md 时间戳 →
若时间戳 < 今日 → 强制展示 diff（旧值→新值清单）→ 主理人确认 → 同步写入
```

## 🔴 净值强制入库 (CRITICAL)
Phase 4 末尾必须调用 `nav_tool(action="record")` 记录净值快照。
```
调用成功 → 审计日志写入 nav_recorded: true
调用失败 → 审计日志写入 nav_recorded: false，报告标记 ⚠️ 未交卷
```

## 🔴 持仓双向同步 (CRITICAL)
`project.md`（前端 SSOT）与 `investors/<id>/portfolios/<id>/portfolio.yaml`（后端引擎配置）必须始终保持一致。

Phase 1 入口比对两边的持仓标的列表：
```
Step 1: 从 project.md 读取持仓标的列表 → md_set
Step 2: 从 portfolio.yaml 读取 assets[].ticker → yaml_set
Step 3: md_set == yaml_set？
        否 → missing_in_yaml = md_set - yaml_set → 自动补齐 portfolio.yaml
              extra_in_yaml = yaml_set - md_set → 标记人工确认
              阻塞直到同步完成
        是 → ✅ 通过，进入 1.1
```

---

## 流程

```
Phase 1: 数据采集（严格串行，每个工具单独调用）
│
│  📖 READ: project.md → 持仓标的 + 观察池 + 网格档位 + 止损位 + 买入位
│           finance_status_card.md → 可用资金 + 资产配比
│           long-term.md → 选股规则 + 市场限制(688/588/300禁入) + 执行窗口
│           investors/<id>/portfolios/<id>/portfolio.yaml → assets 列表
│
│  ┌── 🔴 持仓双向同步 Checkpoint（比对 project.md vs portfolio.yaml）
│  │    通过 → 进入 1.1
│  │    不通过 → 自动补齐 portfolio.yaml / 标记人工确认 → 阻塞直到同步完成
│  │
├── 1.1 sentinel_tool(action="scan") → 哨兵扫描 [等待返回]
├── 1.2 valuation_tool(action="all") → 估值分位 [等待返回]
├── 1.3 market_data_ext_tool(action="northbound", days=5) → 北向资金 [等待返回]
├── 1.4 portfolio_tool(action="summary", investor, portfolio) → 持仓概览 [等待返回]
├── 1.5 check_constraints_tool(action="buy", investor, portfolio, ticker) → 交易约束 [等待返回]
├── 1.6 get_market_data_tool(tickers=[观察池标的]) → 观察池行情 [等待返回]
├── 1.7 market_data_ext_tool(action="dragon_tiger") → 今日龙虎榜 [等待返回]
├── 1.8 news_tool(action="finance") → 板块/个股消息面 [等待返回]
└── 1.9 sentiment_tool(action="analyze", text=<新闻标题>) → 消息面情感 [等待返回]

    ┌── 🔴 Gate Check: 持仓全量校验（比对 project.md vs portfolio_tool 标的集合）
    │    通过 → 进入 Phase 2  不通过 → 打印缺失列表，回退 Phase 1
    │
    └── 📋 Phase 1 数据快照（结构化输出，供Phase2-4使用）:
        {
          "哨兵": "X/8 多/空",
          "持仓标的": ["ticker1","ticker2",...],
          "今日新增": ["ticker"],
          "各标现价": {"ticker": price},
          "总市值": number,
          "现金": number,
          "总资产": number,
          "总浮盈": number,
          "project.md标的数": expected_count,
          "实际标的数": actual_count,
          "对账结果": "✅ 吻合 / ⚠️ 偏差见missing列表"
        }

Phase 2: 策略生成（纯计算 + LCD + 回归测试）
├── 2.1 持仓审计（逐只检查网格/止损/止盈）
├── 2.2 观察池审计（Rule 7 价格到位检查）
├── 2.3 引力热力图：观察池标的 MA 支撑带
├── 2.4 条件单设置计算
├── 2.5 可用资金分配（Rule 2/8/9 约束）
├── 2.6 LCD 检测：每条买入建议 vs 仓位红线
├── 2.7 回归测试标记：验证策略建议通过 rule_scenarios.json
└── 2.8 ⚠️ 龙虎榜预警：检查观察池标的是否被知名游资爆买

Phase 3: 输出生成
│  ✍️ WRITE: project.md → 更新条件单/止损价/网格触发记录（需主理人确认）
│            finance_status_card.md → **强制**更新（需主理人确认）
│
├── 3.1 🔴 强制更新 finance_status_card.md
│       └── 检测状态卡时间戳 < 今日 → 打印 diff → 主理人确认 → 写入
├── 3.2 生成策略报告 → outputs/YYYY-MM-DD-morning-strategy.md
│   ⚠️ **[强制红线]** 生成此报告必须严格按照以下 Markdown 模板，不准自行增加宏观废话：
│   ```markdown
│   # 🔔 Praxis 极简早盘策略 | <YYYY-MM-DD>
│   
│   ## 一、大盘降维 (Sentinel Status)
│   *   **哨兵指令**：<N>/8 (<极寒/适度/亢奋>)
│   *   **资金水位**：可用现金 <XX.X>% | 已用仓位 <XX.X>%
│   *   **纪律限制**：<提取自 Rule 1-10，例如：当前触发 20% 仓位红线限制，绝对禁止动用现金>
│   
│   ## 二、热门板块与资金流向分析 (Sector & Theme Analysis)
│   > **根据 8 哨兵矩阵的最新微观表现，市场呈现出极端的"防守转进攻"资金轮动特征：**
│   
│   *   **🔥 强势进攻（动能主线）**：
│   *   **🧊 资金出逃（防守瓦解）**：
│   *   **🎯 战术指导**：
│   
│   ## 三、持仓与观察池靶心 (Target Grid)
│   | 标的 | 属性 | 昨收 | 成本 | 盈亏% | 关键防守/进攻位 | 今日核心关注 |
│   |------|------|------|------|-------|----------------|--------------|
│   | <名称> | <持仓/观察> | <价格>| <价格>| <比例> | <硬止损/网格买卖点>| <一句话逻辑，如：回踩MA5支撑> |
│   
│   ## 四、今日扣扳机清单 (If-Then Execution)
│   > **[系统强制] 交易前请务必核对底层账本与券商实盘资金一致！**
│   
│   **🚨 卖出/止损预警 (Sell Triggers)：**
│   *   **<标的名称>**：若跌破 <价格> → **<执行动作，例如：硬止损清仓 1100 份>**
│   
│   **🎯 买入/网格指令 (Buy Triggers)：**
│   *   **<标的名称>**：若回踩 <价格> → **<执行动作，例如：买入 500 股>** (受限于可用资金及仓位红线)
│   
│   **⚠️ 特别警报 (Special Alerts)：**
│   *   <提取物理事件，如：今日除权除息、停牌、或即将触碰强压力位。若无则填"无">
│   ```
├── 3.3 更新 project.md 条件单（需主理人确认）
└── 3.4 对话中输出早盘扣扳机清单的精简总结

Phase 4: 审计日志
├── 4.1 写入 outputs/logs/skill-execution.jsonl
│
├── 4.2 🔴 nav_tool(action="record", investor, portfolio) → 【强制】记录当日净值快照
│       └── 成功 → 完成
│       └── 失败 → 审计日志标记 nav_recorded: false，报告标记 ⚠️ 未交卷
```

## MCP 工具调用

```python
# Phase 1: 数据采集（严格串行，每个工具单独调用）
sentinel_tool(action="scan")                                       # 哨兵扫描
valuation_tool(action="all")                                       # 估值分位
market_data_ext_tool(action="northbound", days=5)                  # 北向资金
portfolio_tool(action="summary", investor="demo", portfolio="core")  # 持仓概览
check_constraints_tool(action="buy", investor="demo", portfolio="core", ticker="000001")  # 交易约束
get_market_data_tool(tickers=["600000", "000002", "000003", "000004"])  # 观察池标的
market_data_ext_tool(action="dragon_tiger")                        # 今日龙虎榜
news_tool(action="finance")                                        # 板块消息面
sentiment_tool(action="analyze", text="<新闻标题>")                # 消息面情感
```

## LCD 集成

```bash
python praxis_sdk/cli.py lcd --check trade --ticker <代码> --price <价格> --size <金额>
```

## Error Handling
- Phase 1 任一工具失败 → 重试1次 → 仍失败标记 "⚠️数据缺失"，继续后续Phase
- Phase 4.2 nav_tool 失败 → 审计日志标记 nav_recorded: false，报告标记 ⚠️ 未交卷
- 写文件失败 → 降级为对话输出
- 原则：输出可不完整，绝不伪造
- **Gate Check 失败** → 必须回退 Phase 1 补采，不可跳过
