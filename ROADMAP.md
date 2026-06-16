# PRAXIS ROADMAP

> **版本规划与开发路线图**

---

## 已完成

### v4.0.0 (2026-06-16) — PortfolioParser 重构 + 风控黑名单修复

**状态**: ✅ 已发布

#### 架构修复
- [x] PortfolioParser 完整重构：从持仓表精准解析真实持仓，资金水位推导（total_assets 直接取自行、cash = total_assets - positions_value）
- [x] 科创板风控黑名单修复：`_check_banned_market()` 新增 InvestorConstraints fallback
- [x] BSE 北交所前缀识别（83/87/92/43）
- [x] 17/17 全量测试通过（此前 1 个故障已修复）

---

### v4.0.0 (2026-06-15) — 单工具链式 SOP + 级联复盘 + 状态卡联动

**状态**: ✅ 已完成

#### 核心功能
- [x] Bundle 并发架构彻底清除
- [x] 单工具链式 SOP 确立（9 大场景）
- [x] 状态卡联动矩阵（READ → TOOL → WRITE）
- [x] 级联复盘体系（monthly/quarterly/annual）
- [x] 数据源降级链单点故障隔离
- [x] Skills 全面重写（13 个 Skill）

---

### v3.5.0 (2026-06-14) - 工具整合优化

**状态**: ✅ 已完成

#### 核心功能
- [x] 创建 portfolio_tool（整合 4 → 1）
- [x] 创建 trading_tool（整合 3 → 1）
- [x] 创建 market_data_ext_tool（整合 4 → 1）
- [x] 创建 review_bundle_tool（整合 2 → 1）
- [x] 创建 strategy_tool（整合 3 → 1）
- [x] 创建 evolution_tool（整合 4 → 1）
- [x] 创建 grayscale_tool（整合 2 → 1）
- [x] 创建 team_tool（整合 3 → 1）
- [x] 为旧工具添加 deprecated 标记
- [x] 工具数量：56 → 31（减少 45%）

---

### v3.4.0 (2026-06-14) - Macro-Tool Bundle 效率优化
**状态**: ✅ 已完成

#### 核心功能
- [x] 创建 `health_checker.py` 启动健康检查器
- [x] 添加 5 个 Bundle 工具（market_state/daily_review/weekly_review/trading_session/stock_analysis）
- [x] Bundle 特性：服务端并发 + 客户端串行 + 错误处理 + 进度报告
- [x] 更新 daily-review/weekly-review/trading-session SKILL.md 使用 Bundle
- [x] 预期效果：weekly-review 60-120秒 → 5-15秒（10-20x）

---

### v3.3.0 (2026-06-14) - MCP 稳定性优化 + Stdio 隔离

**状态**: ✅ 已完成

#### 核心功能
- [x] Asyncio 事件循环阻塞修复
- [x] 串行调用约束
- [x] Stdio 管道防污染隔离
- [x] 全局日志抑制

---

### v3.2.0 (2026-06-13) - MCP 稳定性优化

**状态**: ✅ 已完成

- [x] Asyncio 事件循环阻塞修复
- [x] 串行调用约束
- [x] SSE 传输层支持

---

### v3.1.0 (2026-06-13) - 数据源架构重构 + 业务层集成

**状态**: ✅ 已完成

#### 核心功能
- [x] 全局限流器 (令牌桶 + 随机抖动)
- [x] 熔断器 (三态状态机 + 冷却机制)
- [x] TTL 缓存层 (12 小时内不重复请求)
- [x] 东财基类 (UA 伪装 + Session 复用 + 自动重试)

#### 数据源
- [x] MX (API+Key) - Tier 1 绝对主力
- [x] mootdx (TCP) - Tier 2 极速降级
- [x] tencent (HTTP) - Tier 2 备用
- [x] 资金流向数据源 (东财 push2)
- [x] 北向资金数据源 (同花顺)
- [x] 龙虎榜数据源 (东财 datacenter)
- [x] 研报数据源 (东财 reportapi)
- [x] 巨潮公告数据源 (元数据)
- [x] iwen财数据源 (akshare + Playwright)

#### MCP 工具
- [x] `fund_flow_tool` - 资金流向
- [x] `northbound_tool` - 北向资金
- [x] `dragon_tiger_tool` - 龙虎榜
- [x] `research_report_tool` - 研报数据

#### Skill 更新
- [x] `daily-review` - 新增资金流向/北向资金/龙虎榜
- [x] `trading-session` - 新增龙虎榜/资金流向
- [x] `three-team` - 新增研报数据

---

### v3.0.0 (2026-06-10) - Skill + MCP 双引擎

**状态**: ✅ 已完成

- [x] 断点续传机制
- [x] 模型分级 (deep/quick)
- [x] 结构化输出 (Pydantic schema)
- [x] Alpha 追踪
- [x] 延迟反思
- [x] 逻辑硬化 (规则校验下沉)
- [x] LCD 冲突检测

---

## 规划中

### v4.1 — 多组合支持 + 策略回测

**状态**: 📋 规划中

#### 组合管理
- [ ] 多投资者 / 多组合并行管理
- [ ] 组合间对比分析
- [ ] 全局仓位汇总视图
- [ ] 跨组合约束检查

#### 策略引擎
- [ ] 策略回测引擎
- [ ] 历史数据回放
- [ ] 绩效指标计算 (夏普/最大回撤/胜率)

---

### v4.2 — 数据源加固 + 情感进化

**状态**: 📋 规划中

- [ ] 数据源熔断器（单源故障自动降级）
- [ ] 数据质量实时监控仪表盘
- [ ] 历史行情数据本地缓存
- [ ] 情感关键词动态学习
- [ ] 行业专属情感词典（半导体/新能源/消费/金融）

---

### v4.3 — 策略自动化

**状态**: 📋 规划中

- [ ] 自动交易信号生成（哨兵 + 估值 + 情感三因子融合）
- [ ] 止损止盈自动触发
- [ ] 定时任务调度器（盘前/盘中/盘后）
- [ ] 交易执行模拟器（dry-run 模式）

---

### v4.4 — 全自主投研 Agent

**状态**: 📋 规划中

- [ ] Agent 自主决策闭环（感知 → 分析 → 决策 → 执行 → 复盘）
- [ ] 多 Agent 协作（Reasonix + Antigravity + Gemini 联合研判）
- [ ] 元进化引擎 v2（从复盘结果自动优化规则参数）
- [ ] 风控沙盒（新策略先在沙盒跑 30 天再上实盘）

---

## 技术债务

### 已解决
- [x] 数据源防封 (限流器 + 熔断器)
- [x] 缓存机制 (TTL 缓存层)
- [x] 代码重复 (东财基类)

### 待解决
- [ ] 测试覆盖率提升 (目标 80%)
- [ ] 文档完善 (API 文档)
- [ ] 性能优化 (并发请求)

---

## 参考项目

- [go-stock](https://github.com/ArvinLovegood/go-stock) - 6.4k stars
- [a-stock-data](https://github.com/simonlin1212/a-stock-data) - 3.9k stars
- [adata](https://github.com/1nchaos/adata) - 4.7k stars
