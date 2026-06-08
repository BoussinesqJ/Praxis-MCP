# 更新日志

本项目的所有重要更改都将记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本控制](https://semver.org/lang/zh-CN/)。

## [r1.1.0] - 2026-06-08

### 新增
- **AlphaEar 金融技能集成**：新闻聚合、情感分析、股票基本面数据
- `get_finance_news_tool`：10+ 信源实时财经新闻（财联社/华尔街见闻/雪球等）
- `get_unified_trends_tool`：多平台综合热点报告
- `get_polymarket_tool`：Polymarket 预测市场摘要
- `list_news_sources_tool`：列出支持的新闻源
- `analyze_sentiment_tool`：FinBERT 金融情感分析
- `batch_analyze_sentiment_tool`：批量情感分析
- `providers/alphaear_stock_provider.py`：A股/港股/美股基本面数据源插件
- 哨兵雷达引擎（sentinel.py）：8 个哨兵 ETF MA20 多空趋势追踪
- 估值分位引擎（valuation.py）：指数 PE-TTM 历史分位

### 修复
- Tencent 行情 ticker 映射错误（016874 导致后续 ticker 错位）
- Baostock 返回过时数据（改为返回空，强制使用腾讯实时数据）
- `get_market_data_tool` 传递 workspace 参数确保数据源配置正确

### 统计
- MCP 工具：77 → 83（+6）
- MCP 资源：1
- 数据源：4 → 5（+AlphaEar 股票）

## [v1.5.0] - 2026-06-08

### 新增
- **自适应规则引擎**（Phase 3）：从交易/NAV 历史中学习模式，自动生成规则草案
- **长期记忆系统**（Phase 5）：进化记忆归档、时间线生成、类似情况回溯查询
- **多 Agent 协作**（Phase 4）：Agent 决策标准化、共识检查、准确率排名
- `auto_evolve_tool`：一键自进化（评估→建议→备份→待审批）
- `learn_rules_tool` / `list_learned_rules_tool` / `approve_rule_tool` / `reject_rule_tool`
- `record_evolution_memory_tool` / `get_evolution_timeline_tool` / `query_evolution_memory_tool`
- `record_agent_decision_tool` / `check_consensus_tool` / `rank_agents_tool`
- 事件驱动闭环：交易完成后自动触发进化评估 + 规则学习

### 改进
- **Lazy Import 优化**：MCP Server 启动不加载工具模块，首次调用时延迟加载
- Logger 延迟初始化（首次写操作时才加载）
- 约束引擎策略驱动：从策略文件读取禁入板块/工具/持仓上限/现金底线
- 冲销交易过滤：`filter_active_transactions()` 应用到 4 个持仓计算文件
- 净值快照修复：合并 3 次账本遍历为 1 次 + 补充分红计算
- 盈亏比改为按单笔交易计算（非净盈亏）
- 下行波动率改为 Sortino 标准公式
- 缓存 TTL 生效 + 文件缓存启动时加载
- 14 个工具 docstring 添加 `discover_workspace_tool()` 引导提示

### 修复
- `reverse()` 增加双重冲销/分红冲销防护
- `_check_banned_instrument` 和 `_check_position_cap` 从空壳改为策略驱动实现
- ETF 检测改为精确前缀匹配（防止 150xxx 杠杆基金误豁免）
- 腾讯 API HTTPS 升级（5 处 http→https）
- `record_nav_tool` 防御性 ValidationError 处理
- 场外基金 NAV fallback（AKShare/东方财富）
- 决策→交易引用完整性验证
- Prompt diff 算法支持插入/删除行

### 统计
- MCP 工具：63 → 74（+11）
- MCP 资源：1
- 测试用例：111 passed
- 自进化闭环：3 个断点全部接通

## [r1.0.0] - 2026-06-08

### 新增
- 开源版本发布
- 基于 v1.4 版本，重命名为 r1.0.0
- 添加 MIT 开源协议
- 添加贡献指南

### 功能特性
- 63 个 MCP 工具
- 1 个 MCP 资源
- 17 个 CLI 命令组
- 418 个测试用例
- 4 个数据源（AKShare/Baostock/东方财富/腾讯）+ 用户插件
- 自动发现 Workspace 功能
- 场外基金支持
- 腾讯 API HTTPS 升级

### 技术改进
- 多源数据源插件化架构
- Agent 引导优化
- 14 个工具添加 `discover_workspace_tool()` 引导提示

## [v1.4.0] - 2026-06-08

### 新增
- `discover_workspace_tool`：零参数自动发现投资者/组合/持仓/状态/推荐下一步
- `praxis://workspace/discovery`：Workspace 元数据，连接握手时自动暴露

### 修复
- 实盘测试修复
- 场外基金支持
- 腾讯 API HTTPS 升级

## [v1.3.0] - 2026-06-08

### 新增
- 多源数据源插件化架构
- AKShare + Baostock + 用户插件支持

## [v1.2.0] - 2026-06-08

### 新增
- 数据接入增强
- 引擎合并
- 安全加固

### 改进
- 工具数量增加到 62 个

## [v1.1.0] - 2026-06-05

### 新增
- 测试强化：329 测试
- 交易摩擦/数据质量/Prompt版本工具

## [v1.0.0] - 2026-05

### 新增
- 基础版本：MCP Server + 40 工具 + CLI
- 投研纪律系统核心功能