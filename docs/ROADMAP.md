# PRAXIS 开发路线图

> 最后更新：2026-06-08（r1.0.0）

---

## 当前状态

| 指标 | 数值 |
|:----:|:----:|
| 版本 | r1.0.0 |
| MCP 工具 | 63 |
| MCP 资源 | 1 |
| CLI 命令组 | 17 |
| 测试用例 | 418 |
| 数据源 | 4（AKShare/Baostock/东方财富/腾讯）+ 用户插件 |

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|:----:|:----:|---------|
| v1.0.0 | 2026-05 | 基础版本：MCP Server + 40 工具 + CLI |
| v1.1 | 2026-06-05 | 测试强化：329 测试 + 交易摩擦/数据质量/Prompt版本工具 |
| v1.2 | 2026-06-08 | 数据接入增强 + 引擎合并 + 安全加固：62 工具 |
| v1.3 | 2026-06-08 | 多源数据源插件化架构：AKShare + Baostock + 用户插件 |
| r1.0.0 | 2026-06-08 | 开源版本：基于 v1.4，重命名为 r1.0.0，添加开源协议 |

---

## r1.0.0 变更摘要

### 新增 MCP 工具（1 个）
- `discover_workspace_tool`：零参数自动发现投资者/组合/持仓/状态/推荐下一步

### 新增 MCP 资源（1 个）
- `praxis://workspace/discovery`：Workspace 元数据，连接握手时自动暴露

### 场外基金支持
- `get_state_tool`、`get_portfolio_summary_tool`、`nav_tracker` 增加 `get_fund_nav()` fallback
- 当 `get_realtime_quote` 返回 `price=0` 时自动尝试基金净值（AKShare/东方财富）

### 腾讯 API HTTPS 升级
- 修复 5 处 `http://qt.gtimg.cn` → `https://qt.gtimg.cn`（腾讯强制 HTTPS）

### Agent 引导优化
- 14 个工具 docstring 添加 `discover_workspace_tool()` 引导提示
- MCP Resource 支持客户端自动发现 workspace 信息

### 防御性改进
- `record_nav_tool` 增加 `ValidationError` 专项捕获 + 可操作错误提示

### Bug 修复
- 修复双 Workspace 路径混乱（PRAXIS_WORKSPACE 环境变量）
- 修复 team prompt 加载不完整（teams/ 目录结构对齐）
- 修复场外基金 FUND_A 市值为 0 的问题
- 修复绩效 tag 隔离导致买卖配对断裂

### 测试
- 新增 `test_workspace.py`：41 个测试用例
- 总测试数：349 → 418（+69）

---

## v1.3 变更摘要

### 多源数据源插件化
- 新增数据源注册表（`praxis/engine/data/registry.py`）
- AKShare 适配器（东方财富/新浪/同花顺聚合，需 `pip install akshare`）
- Baostock 适配器（交易所直连，需 `pip install baostock`）
- 用户插件目录（`providers/`，自动发现 + 优先级链）
- 健康检查：连续失败 3 次自动标记 unhealthy
- 可选依赖：`pip install praxis[akshare]` / `praxis[baostock]` / `praxis[all]`

### 容错策略
```
AKShare(10) → Baostock(20) → 东方财富(50) → 腾讯(80) → 用户插件(90+) → 本地缓存
```

### Bug 修复
- README CLI 示例修正（market quote → market）
- 版本号统一（cli.py / __init__.py → 1.3.0）

---

## v1.2 变更摘要

### 新增 MCP 工具（9 个）
- 投资者管理: create_investor / create_portfolio / init_investor
- 审批流程: approve_transaction / reject_transaction / list_pending_transactions
- 数据清理: delete_transaction / purge_ledger
- 聚合概览: get_portfolio_summary

### 架构改进
- Transaction 模型新增 `tags`（标签过滤）和 `asset_type`（资产类型）
- PerformanceCalculator 支持 `exclude_reversed` / `exclude_tags` / `include_tags` / `ticker` 过滤
- get_state_tool 新增 `infer_from_ledger` 纯推断模式
- 引擎层消除并行实现：合并 `engine/` 与 `engine/execution/`
- 新增东方财富数据源（零 API Key）

### 安全加固
- 新增 `praxis/core/validation.py` 路径校验工具
- config_loader 全入口路径遍历防护
- .gitignore 清理 + 敏感文件排除

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
| Workspace 盲飞 | r1.0.0 | discover_workspace_tool + MCP Resource |
| 场外基金隐形 | r1.0.0 | get_fund_nav fallback |
| 腾讯 API 302 | r1.0.0 | HTTP → HTTPS 升级 |

---

## 总体原则

- V1 不做重型实现，但必须把边界定义好
- 每个新实体先定义 Schema，再实现
- 每个写操作都带幂等键 + 审计日志
- 每个功能都要有测试验证
- 每次推送 GitHub 必须安全审查 + 用户二次确认
