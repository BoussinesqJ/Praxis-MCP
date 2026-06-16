# Praxis Roadmap

## v4.0 — PortfolioParser 重构 + 风控黑名单修复 ✅ (2026-06-16)

- [x] PortfolioParser 完整重构：从持仓表精准解析真实持仓，资金水位推导（total_assets 直接取自行、cash = total_assets - positions_value）
- [x] 科创板风控黑名单修复：`_check_banned_market()` 新增 InvestorConstraints fallback
- [x] BSE 北交所前缀识别（83/87/92/43）
- [x] 17/17 全量测试通过

## v3.6 — 单工具链式 SOP + 级联复盘 + 状态卡联动 ✅ (2026-06-15)

- [x] Bundle 并发架构彻底清除（5 个函数物理删除，28 个活跃工具）
- [x] 单工具链式 SOP（9 大场景，SOP_INDEX.md）
- [x] 级联复盘体系（monthly/quarterly/annual，cascade_review_tool）
- [x] 状态卡联动矩阵（READ → TOOL → WRITE）
- [x] 毒教材焚书（7 个旧文档物理删除，12 个归档到 archive/）
- [x] SOP Index 文档金字塔（Tier 0-3 四级优先级）
- [x] AlphaEar 新闻集成（NewsNow API，10+ 信源，10s 超时保护）
- [x] 增强关键词情感分析（否定翻转，93% 命中率，<0.1s）
- [x] Skills 全面重写（13 个 Skill，v3.6.0）

## v4.1 — 多组合支持 🔜

- [ ] 多投资者 / 多组合并行管理
- [ ] 组合间对比分析
- [ ] 全局仓位汇总视图
- [ ] 跨组合约束检查

## v4.2 — 数据源加固 + 情感进化 🔜

- [ ] 数据源熔断器（单源故障自动降级）
- [ ] 数据质量实时监控仪表盘
- [ ] 历史行情数据本地缓存（减少 API 调用）
- [ ] 情感关键词动态学习（从历史预测结果中自动扩充词库）
- [ ] 行业专属情感词典（半导体/新能源/消费/金融）

## v4.3 — 策略自动化 📋

- [ ] 自动交易信号生成（哨兵 + 估值 + 情感三因子融合）
- [ ] 止损止盈自动触发
- [ ] 定时任务调度器（盘前/盘中/盘后自动执行）
- [ ] 交易执行模拟器（dry-run 模式）

## v4.4 — 全自主投研 Agent 📋

- [ ] Agent 自主决策闭环（感知 → 分析 → 决策 → 执行 → 复盘）
- [ ] 多 Agent 协作（Reasonix + Antigravity + Gemini 联合研判）
- [ ] 元进化引擎 v2（从复盘结果自动优化规则参数）
- [ ] 风控沙盒（新策略先在沙盒跑 30 天再上实盘）

## 技术债清理

- [ ] mcp_server.py 拆分（按功能域拆模块）
- [ ] 单元测试覆盖率 > 80%
- [ ] CI/CD 流水线（GitHub Actions）
- [ ] 类型标注补全（mypy strict mode）
- [ ] 废弃工具代码物理删除（23 个 deprecated 工具待清理）

## 数据源扩展

| 数据源 | 状态 | 优先级 |
|:---|:---|:---|
| 东方财富 API | ✅ 已集成 | — |
| akshare | ✅ 已集成 | — |
| baostock | ✅ 已集成 | — |
| 妙想 API | ✅ 已集成 | — |
| NewsNow API | ✅ v3.5 集成 | — |
| Polymarket | ⚠️ 国内不可达 | 低 |
| Tushare Pro | 📋 待评估 | 中 |
| 通达信本地数据 | 📋 待评估 | 低 |

---

> 更新频率：每个版本发布时同步更新
> 最后更新：2026-06-16 (v4.0.0)
