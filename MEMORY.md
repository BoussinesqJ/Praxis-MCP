# MEMORY.md - Praxis 系统记忆

## 系统状态

**当前版本**: v3.5.0
**最后更新**: 2026-06-14
**状态**: ✅ 全部修复完成

## 已修复的问题

### 2026-06-14 - Bundle 工具 Bug

**问题**: Bundle 工具返回协程对象而非实际数据
**原因**: `run_in_safe_thread` 包装 async 函数
**修复**: 直接调用 async 函数
**状态**: ✅ 已修复

### 2026-06-14 - news_tool 宕机

**问题**: AlphaEar 新闻工具未安装
**修复**: 降级到 akshare 简化版
**状态**: ✅ 已修复

### 2026-06-14 - sentiment_tool 宕机

**问题**: AlphaEar 情感分析工具未安装
**修复**: 降级到关键词分析
**状态**: ✅ 已修复

### 2026-06-14 - 工具注册优化

**问题**: 用户看到 56 个工具（包含 deprecated）
**原因**: `_register_tools` 函数注册了所有工具，包括 deprecated
**修复**: 更新 `_register_tools` 函数，跳过 deprecated 工具
**状态**: ✅ 已修复

## 可用工具

### 核心工具（23 个）

**独立工具（15 个）**:
- discover_workspace_tool
- get_market_data_tool
- get_performance_tool
- reconcile_tool
- check_constraints_tool
- nav_tool
- sentinel_tool
- valuation_tool
- sentiment_tool
- news_tool
- benchmark_tool
- agent_tracking_tool
- review_tool
- trading_friction_tool

**整合工具（8 个）**:
- portfolio_tool
- trading_tool
- market_data_ext_tool
- review_bundle_tool
- strategy_tool
- evolution_tool
- grayscale_tool
- team_tool

**Bundle 工具（5 个）**:
- market_state_bundle_tool
- daily_review_bundle_tool
- weekly_review_bundle_tool
- trading_session_bundle_tool
- stock_analysis_bundle_tool

## 数据源优先级

**主数据源**: 妙想 API (MX_APIKEY) — 最准确，API + Key 模式
**降级链**: 妙想 → akshare（静态数据）→ 关键词匹配

### news_tool 数据源
- **优先**: 妙想 API (news_mx.py)
- **降级**: akshare 简化版 (news_akshare.py) — 静态示例数据，不发真实请求
- **决议**: 暂不申请新 API，新闻是噪音，专注盘面数据

### sentiment_tool 数据源
- **优先**: 妙想 API (sentiment_mx.py) — 财务指标分析（基本面因子化）
- **降级**: 关键词匹配 (sentiment_keyword.py)
- **决议**: 保留财务指标推断逻辑，比 NLP 情绪分析更精准

**MCP 服务器**: python praxis/mcp_server.py
**PRAXIS_TOOLS_TIER**: core（默认，跳过 deprecated）

## 文档

- 诊断报告: docs/praxis_diagnostic_report.md
- 修复报告: docs/praxis_fix_report.md
- 架构图: docs/praxis_architecture.txt
- 使用手册: docs/praxis_skill_mcp_manual.md
- 快速参考: docs/praxis_quick_reference.md
