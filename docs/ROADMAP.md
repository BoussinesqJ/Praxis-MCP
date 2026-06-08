# PRAXIS 开发路线图

> 最后更新：2026-06-08（v1.6.0）

---

## 当前状态

| 指标 | 数值 |
|:----:|:----:|
| 版本 | v1.6.0 |
| MCP 工具 | 83 |
| MCP 资源 | 1 |
| CLI 命令组 | 17 |
| 测试用例 | 111 |
| 数据源 | 5（AKShare/Baostock/东方财富/腾讯/AlphaEar）+ 用户插件 |

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|:----:|:----:|---------|
| v1.0.0 | 2026-05 | 基础版本：MCP Server + 40 工具 + CLI |
| v1.1 | 2026-06-05 | 测试强化：329 测试 + 交易摩擦/数据质量/Prompt版本工具 |
| v1.2 | 2026-06-08 | 数据接入增强 + 引擎合并 + 安全加固：62 工具 |
| v1.3 | 2026-06-08 | 多源数据源插件化架构：AKShare + Baostock + 用户插件 |
| v1.4 | 2026-06-08 | Workspace 自动发现 + 场外基金支持 + 实盘测试修复 |
| v1.5 | 2026-06-08 | 自进化架构（Phase 1-5）+ Lazy Import + 事件驱动闭环 |
| v1.6 | 2026-06-08 | AlphaEar 金融技能集成 + 哨兵/估值引擎 + 行情数据修复 |

---

## v1.6 变更摘要

### AlphaEar 金融技能集成
- `get_finance_news_tool`：10+ 信源实时财经新闻
- `get_unified_trends_tool`：多平台综合热点报告
- `get_polymarket_tool`：Polymarket 预测市场摘要
- `analyze_sentiment_tool` / `batch_analyze_sentiment_tool`：FinBERT 情感分析
- `providers/alphaear_stock_provider.py`：A股/港股/美股基本面数据源

### 新增引擎
- 哨兵雷达引擎（sentinel.py）：8 个哨兵 ETF MA20 多空趋势追踪
- 估值分位引擎（valuation.py）：指数 PE-TTM 历史分位

### 行情数据修复
- Tencent ticker 映射错误（016874 导致后续 ticker 错位）
- Baostock 返回过时数据（改为返回空，强制使用腾讯实时数据）
- `get_market_data_tool` 传递 workspace 参数

---

## v1.5 变更摘要

### 自进化架构（Phase 1-5）
- **Phase 1**：Lazy Import 启动优化
- **Phase 2**：`auto_evolve_tool` 一键自进化
- **Phase 3**：自适应规则引擎（adaptive_rules.py）
- **Phase 4**：多 Agent 协作（consensus.py + agent_tracker.py）
- **Phase 5**：长期记忆（evolution_memory.py + memory.py）

### 事件驱动闭环
- `add_transaction` → `auto_evolve` → `record_evolution_memory` → `learn_rules`
- 3 个断点全部接通

### 约束引擎策略驱动
- 从策略文件读取禁入板块/工具/持仓上限/现金底线
- 冲销交易过滤（`filter_active_transactions`）
- 盈亏比改为按单笔交易计算

---

## v1.4 变更摘要

### Workspace 自动发现
- `discover_workspace_tool`：零参数自动发现投资者/组合/状态
- `praxis://workspace/discovery`：MCP Resource

### 场外基金支持
- `get_fund_nav()` fallback（AKShare/东方财富）

### 实盘测试修复
- 双 Workspace 路径混乱
- team prompt 加载不完整
- 绩效 tag 隔离导致买卖配对断裂

---

## R0-R5 核心功能 ✅

| 阶段 | 内容 | 状态 |
|:----:|------|:----:|
| R0 | 文档收敛 + 数据边界确认 | ✅ |
| R1 | 只读 MCP + CLI + dry-run 对账 | ✅ |
| R2 | 交易账本 + 审批 + 状态重建 | ✅ |
| R3 | Decision Record + 绩效指标 | ✅ |
| R4 | 完整 MCP + AI 团队集成 | ✅ |
| R5 | 进化引擎 + Prompt 管理 | ✅ |

---

## 技术债务清零 ✅

| 问题 | 版本 | 说明 |
|------|:----:|------|
| asyncio 冲突 | v1.1 | 已修复 |
| 缺少错误处理 | v1.1 | 所有工具 try-catch |
| 缺少日志系统 | v1.1 | praxis/core/logger.py |
| 缺少配置验证 | v1.1 | praxis/core/config_validator.py |
| 并行引擎重复 | v1.2 | 合并 engine/ 与 engine/execution/ |
| 配置文件死循环 | v1.2 | init_investor_tool 解决 |
| 审批流程空壳 | v1.2 | pending.jsonl 持久化 |
| 绩效数据失真 | v1.2 | 标签过滤/冲销排除 |
| 路径遍历漏洞 | v1.2 | validate_id 全入口覆盖 |
| 数据源单一 | v1.3 | 多源插件化架构 |
| Workspace 盲飞 | v1.4 | discover_workspace_tool + MCP Resource |
| 场外基金隐形 | v1.4 | get_fund_nav fallback |
| 腾讯 API 302 | v1.4 | HTTP → HTTPS 升级 |
| 约束引擎空壳 | v1.5 | 策略驱动禁入板块/工具/持仓上限 |
| 冲销交易污染 | v1.5 | filter_active_transactions |
| 自进化闭环断裂 | v1.5 | 3 个断点衔接 |
| 行情 ticker 错位 | v1.6 | Tencent 解析修复 |
| Baostock 过时数据 | v1.6 | 改为返回空，强制腾讯 |
| 新闻/情感能力缺失 | v1.6 | AlphaEar 集成 |

---

## 总体原则

- V1 不做重型实现，但必须把边界定义好
- 每个新实体先定义 Schema，再实现
- 每个写操作都带幂等键 + 审计日志
- 每个功能都要有测试验证
- 每次推送 GitHub 必须安全审查 + 用户二次确认
