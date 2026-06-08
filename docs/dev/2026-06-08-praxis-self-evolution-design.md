# Praxis 自进化架构设计文档

> **日期**: 2026-06-08
> **状态**: ✅ 全部完成
> **范围**: Phase 3-5（自适应规则 / 多 Agent 协作 / 长期记忆）
> **前置**: Phase 1 (Lazy Import ✅) + Phase 2 (auto_evolve_tool ✅)

---

## 一、架构总览

### 1.1 设计理念

Praxis 不应是被动的工具，而是主动的投研伙伴。核心闭环：

```
事件触发 → 数据驱动评估 → 机器提议 → 人类审批 → 执行 + 学习
    ↑                                                    ↓
    └────────────── 经验沉淀 ←────────────────────────────┘
```

### 1.2 已完成 vs 待实施

| Phase | 内容 | 状态 | 本文档覆盖 |
|:---:|:---|:---:|:---:|
| 1 | Lazy Import 启动优化 | ✅ | — |
| 2 | auto_evolve_tool 进化触发器 | ✅ | — |
| **3** | **自适应规则引擎** | ✅ | ✅ |
| **4** | **多 Agent 协作优化** | ✅ | ✅ |
| **5** | **长期记忆与知识沉淀** | ✅ | ✅ |

### 1.3 事件驱动架构

```
┌─────────────────────────────────────────────────────────┐
│                    事件源 (Event Sources)                 │
│                                                          │
│  add_transaction_tool ──→ 写入完成事件                    │
│  record_nav_tool      ──→ NAV 记录事件                   │
│  check_constraints    ──→ 约束触发事件                    │
│  定时器 (每日收盘后)   ──→ 日终事件                       │
├─────────────────────────────────────────────────────────┤
│                    事件路由器 (Event Router)              │
│                                                          │
│  事件类型 → 触发条件检查 → 分发到处理器                   │
├─────────────────────────────────────────────────────────┤
│                    处理器 (Handlers)                      │
│                                                          │
│  Phase 3: 规则学习器 → 自适应规则生成                     │
│  Phase 4: Agent 协调器 → 多引擎共识                       │
│  Phase 5: 记忆沉淀器 → 知识归档                           │
└─────────────────────────────────────────────────────────┘
```

---

## 二、Phase 3：自适应规则引擎

### 2.1 目标

从历史决策记录中提取模式，自动生成规则草案，经过安全扫描后提交审批。

### 2.2 规则格式

```yaml
# teams/adaptive/learned_rules.md 中的结构化规则
rules:
  - id: rule_001
    name: "止损后反弹规律"
    condition: |
      IF 最近5笔交易中止损触发 ≥ 2 次
      AND 止损后5个交易日内价格回升 ≥ 5%
      AND 标的PE < 行业中位数
    action: "建议放宽止损线从 -10% 到 -12%"
    confidence: 0.72
    hit_count: 3
    miss_count: 1
    source_decisions: ["tx-20260601-003", "tx-20260605-001"]
    created_at: "2026-06-08"
    status: "active"  # draft | active | retired
```

### 2.3 规则类型

| 类型 | 条件 | 动作 | 数据源 |
|:---|:---|:---|:---|
| **止损调优** | 止损后反弹率 > 60% 且 ≥ 3 次 | 建议放宽/收紧止损线 | ledger + nav |
| **网格间距** | 平均触发间隔 < 5 天或 > 30 天 | 建议调整网格间距 | ledger |
| **现金底线** | 现金比例持续 > 60% 且机会成本高 | 建议降低底线 | nav + performance |
| **持仓集中** | 单标的占比接近 15% 上限 | 建议分散或冻结加仓 | state |
| **情绪防御** | 连续 3 天下跌 + 恐慌卖出信号 | 锁仓提醒 | nav + market |

### 2.4 规则学习流程

```python
class AdaptiveRuleEngine:
    """自适应规则引擎"""

    def __init__(self, workspace: str):
        self.workspace = workspace
        self.rules_path = Path(workspace) / "teams" / "adaptive" / "learned_rules.md"
        self.decision_path = Path(workspace) / "data" / "decisions" / "decision_records.jsonl"
        self.ledger_path = Path(workspace) / "data" / "ledger" / "transactions.jsonl"

    def learn(self) -> list[dict]:
        """从历史数据中学习规则"""
        rules = []

        # 1. 分析止损触发模式
        rules.extend(self._learn_stop_loss_patterns())

        # 2. 分析网格触发频率
        rules.extend(self._learn_grid_spacing_patterns())

        # 3. 分析现金利用率
        rules.extend(self._learn_cash_utilization_patterns())

        # 4. 安全扫描每条规则
        from praxis.engine.prompt_scanner import PromptScanner
        scanner = PromptScanner()
        safe_rules = []
        for rule in rules:
            scan = scanner.scan_content(rule["condition"], "adaptive_rule")
            if scan.is_safe:
                safe_rules.append(rule)
            else:
                rule["status"] = "rejected_by_scanner"
                rule["scan_result"] = scan.model_dump()

        return safe_rules

    def _learn_stop_loss_patterns(self) -> list[dict]:
        """学习止损模式"""
        # 读取所有止损触发的交易
        # 检查触发后 5 天内的价格变化
        # 如果反弹率 > 60% 且 ≥ 3 次，生成规则草案
        ...

    def _learn_grid_spacing_patterns(self) -> list[dict]:
        """学习网格间距模式"""
        # 计算同类标的的平均触发间隔
        # 如果 < 5 天，建议放宽间距
        # 如果 > 30 天，建议收紧间距
        ...

    def _learn_cash_utilization_patterns(self) -> list[dict]:
        """学习现金利用率模式"""
        # 读取 NAV 历史
        # 计算现金比例趋势
        # 如果持续 > 60%，建议降低底线
        ...
```

### 2.5 实现步骤

| 步骤 | 文件 | 工作量 |
|:---|:---|:---:|
| 创建 `praxis/engine/adaptive_rules.py` | 新建 | ~200 行 |
| 创建 `praxis/tools/adaptive.py` | 新建 | ~60 行 |
| 注册 `learn_rules_tool` + `list_learned_rules_tool` | mcp_server.py | +10 行 |
| 扩展 `teams/adaptive/learned_rules.md` 格式 | 文档 | ~30 行 |
| 测试 `tests/test_adaptive.py` | 新建 | ~80 行 |

### 2.6 触发时机

```
auto_evolve_tool 调用后
  → 自动调用 learn_rules()
  → 新规则写入 learned_rules.md（draft 状态）
  → 通知用户审批
  → 审批通过后 status → active
```

---

## 三、Phase 4：多 Agent 协作优化

### 3.1 目标

标准化不同 AI Agent 的分析结果，比较建议质量，自动选择最优 Agent。

### 3.2 Agent 标准化接口

```python
class AgentDecision(BaseModel):
    """标准化 Agent 决策记录"""
    agent_id: str           # "reasonix" / "gemini" / "claude"
    timestamp: str          # ISO 时间戳
    ticker: str             # 标的代码
    action: str             # buy / sell / hold / watch
    confidence: float       # 0.0 - 1.0
    reasoning: str          # 决策理由
    price_target: float | None = None
    stop_loss: float | None = None
    time_horizon: str = "short"  # short / medium / long
    source_team: str = ""   # "asrg" / "masters" / "trading"
```

### 3.3 Agent 准确率追踪

扩展现有 `ai_tracker` 模块：

```python
class AgentTracker:
    """Agent 准确率追踪器"""

    def record_decision(self, decision: AgentDecision) -> str:
        """记录 Agent 决策"""
        # 写入 data/agent_decisions/{agent_id}.jsonl
        ...

    def evaluate_agent(self, agent_id: str, lookback_days: int = 30) -> dict:
        """评估 Agent 准确率"""
        # 读取最近 N 天的决策
        # 与实际价格走势对比
        # 计算：方向准确率、时机准确率、置信度校准
        return {
            "agent_id": agent_id,
            "direction_accuracy": 0.65,  # 方向判断准确率
            "timing_accuracy": 0.45,     # 时机判断准确率
            "confidence_calibration": 0.82,  # 置信度与实际准确率的吻合度
            "total_decisions": 42,
            "evaluated": 30,
        }

    def rank_agents(self) -> list[dict]:
        """排名所有 Agent"""
        # 按综合得分排序
        ...
```

### 3.4 共识机制

```python
class ConsensusEngine:
    """多 Agent 共识引擎"""

    def check_consensus(
        self,
        ticker: str,
        decisions: list[AgentDecision],
        min_agents: int = 2,
    ) -> dict:
        """检查多 Agent 共识"""
        # 统计 action 分布
        action_counts = {}
        for d in decisions:
            action_counts[d.action] = action_counts.get(d.action, 0) + 1

        # 找到最高票 action
        top_action = max(action_counts, key=action_counts.get)
        top_count = action_counts[top_action]
        total = len(decisions)

        consensus = top_count >= min_agents

        return {
            "ticker": ticker,
            "consensus": consensus,
            "recommended_action": top_action,
            "vote_distribution": action_counts,
            "total_agents": total,
            "consensus_ratio": top_count / total,
            "message": (
                f"{'达成共识' if consensus else '未达共识'}: "
                f"{top_action} ({top_count}/{total} agents)"
            ),
        }
```

### 3.5 实现步骤

| 步骤 | 文件 | 工作量 |
|:---|:---|:---:|
| 扩展 `praxis/engine/ai_tracker.py` | 修改 | +100 行 |
| 创建 `praxis/engine/consensus.py` | 新建 | ~80 行 |
| 创建 `praxis/tools/agent_tracker.py` | 新建 | ~60 行 |
| 注册 `record_agent_decision_tool` + `check_consensus_tool` | mcp_server.py | +15 行 |
| 测试 `tests/test_consensus.py` | 新建 | ~50 行 |

### 3.6 数据目录

```
data/
  agent_decisions/
    reasonix.jsonl      # Reasonix 的决策记录
    gemini.jsonl        # Gemini 的决策记录
    claude.jsonl        # Claude 的决策记录
  consensus/
    reports/            # 共识报告归档
```

---

## 四、Phase 5：长期记忆与知识沉淀

### 4.1 目标

将每次进化审计归档为结构化知识，建立策略进化时间线，支持回溯查询。

### 4.2 知识结构

```python
class EvolutionMemory(BaseModel):
    """进化记忆记录"""
    memory_id: str              # "evo-20260608-001"
    timestamp: str
    trigger_event: str          # "transaction" / "nav_record" / "sentinel" / "manual"
    strategy_name: str
    evaluation_summary: str     # 评估摘要
    dimensions: list[dict]      # 维度状态快照
    suggestions: list[dict]     # 进化建议
    decision: str               # "approved" / "rejected" / "pending"
    rejection_reason: str | None = None
    outcome: str | None = None  # 审批后实际效果（延迟回填）
    outcome_metrics: dict | None = None  # 效果指标
```

### 4.3 进化时间线

```
deliverables/evolution/
  timeline.md                 # 自动生成的进化时间线
  evolve_grid_value_20260608_143000.md  # 单次评估报告
  evolve_grid_value_20260615_090000.md
  ...
```

`timeline.md` 自动生成格式：

```markdown
# 策略进化时间线: grid_value

| 日期 | 触发事件 | 维度 | 决策 | 效果 |
|:---|:---|:---|:---:|:---|
| 2026-06-08 | 交易后触发 | stop_loss_tightness: critical | pending | — |
| 2026-06-01 | NAV 记录 | cash_floor: warning | approved | 现金比例 89%→65% |
| 2026-05-25 | 手动触发 | grid_spacing: healthy | no_action | — |
```

### 4.4 回溯查询

```python
class EvolutionMemoryStore:
    """进化记忆存储"""

    def __init__(self, workspace: str):
        self.memory_dir = Path(workspace) / "data" / "evolution_memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def record(self, memory: EvolutionMemory) -> str:
        """记录进化记忆"""
        path = self.memory_dir / f"{memory.memory_id}.json"
        path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def query_similar(self, situation: str, limit: int = 5) -> list[dict]:
        """查询类似情况的历史进化记录

        简单实现：按触发事件 + 维度名称匹配。
        后续可升级为向量相似度搜索。
        """
        memories = self._load_all()
        # 按维度名称匹配
        scored = []
        for m in memories:
            score = sum(
                1 for d in m.dimensions
                if d["name"] in situation
            )
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m.model_dump() for _, m in scored[:limit]]

    def generate_timeline(self, strategy_name: str) -> str:
        """生成进化时间线 Markdown"""
        memories = sorted(
            [m for m in self._load_all() if m.strategy_name == strategy_name],
            key=lambda m: m.timestamp,
        )
        lines = [
            f"# 策略进化时间线: {strategy_name}",
            "",
            "| 日期 | 触发事件 | 维度 | 决策 | 效果 |",
            "|:---|:---|:---|:---:|:---|",
        ]
        for m in memories:
            dims = ", ".join(d["name"] for d in m.dimensions)
            outcome = m.outcome or "—"
            lines.append(
                f"| {m.timestamp[:10]} | {m.trigger_event} | {dims} | {m.decision} | {outcome} |"
            )
        return "\n".join(lines)
```

### 4.5 实现步骤

| 步骤 | 文件 | 工作量 |
|:---|:---|:---:|
| 创建 `praxis/engine/evolution_memory.py` | 新建 | ~150 行 |
| 创建 `praxis/tools/memory.py` | 新建 | ~50 行 |
| 注册 `query_evolution_memory_tool` + `get_evolution_timeline_tool` | mcp_server.py | +10 行 |
| 修改 `auto_evolve_tool` 增加记忆记录 | evolution.py | +20 行 |
| 测试 `tests/test_evolution_memory.py` | 新建 | ~60 行 |

---

## 五、事件触发器详细设计

### 5.1 触发器注册表

```python
# praxis/engine/event_triggers.py

TRIGGERS = {
    "transaction_completed": [
        "auto_evolve",       # 交易后自动评估进化维度
        "learn_rules",       # 交易后学习新规则
    ],
    "nav_recorded": [
        "auto_evolve",       # NAV 记录后评估
    ],
    "constraint_triggered": [
        "record_agent_decision",  # 约束触发时记录
    ],
    "daily_close": [
        "auto_evolve",       # 日终全面评估
        "generate_timeline", # 更新时间线
    ],
}
```

### 5.2 触发器实现

```python
class EventRouter:
    """事件路由器"""

    def __init__(self, workspace: str):
        self.workspace = workspace
        self._handlers: dict[str, list[Callable]] = {}

    def register(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def emit(self, event_type: str, context: dict):
        """触发事件"""
        handlers = self._handlers.get(event_type, [])
        results = []
        for handler in handlers:
            try:
                result = await handler(context)
                results.append({"handler": handler.__name__, "result": result})
            except Exception as e:
                results.append({"handler": handler.__name__, "error": str(e)})
        return results
```

### 5.3 集成到 add_transaction_tool

在 `praxis/tools/ledger.py` 的 `add_transaction` 函数末尾：

```python
# 交易完成后触发进化评估（非阻塞）
if auto_approve:
    try:
        from praxis.tools.evolution import auto_evolve
        # 异步触发，不阻塞返回
        auto_evolve(strategy_name, investor, portfolio, workspace)
    except Exception:
        pass  # 进化触发失败不影响交易结果
```

---

## 六、测试计划

### Phase 3 测试

```
tests/test_adaptive.py
  - test_learn_stop_loss_pattern      # 止损模式学习
  - test_learn_grid_spacing_pattern   # 网格间距学习
  - test_rule_safety_scan             # 规则安全扫描
  - test_rule_status_transitions      # draft → active → retired
  - test_no_pattern_returns_empty     # 无模式时返回空
```

### Phase 4 测试

```
tests/test_consensus.py
  - test_consensus_achieved           # 2/3 agents agree
  - test_consensus_not_achieved       # no majority
  - test_agent_ranking                # agent accuracy ranking
  - test_decision_recording           # record + retrieve
  - test_confidence_calibration       # confidence vs accuracy
```

### Phase 5 测试

```
tests/test_evolution_memory.py
  - test_record_and_retrieve          # 记录 + 查询
  - test_query_similar                # 类似情况查询
  - test_timeline_generation          # 时间线生成
  - test_memory_after_evolve          # auto_evolve 后自动记录
```

---

## 七、实施顺序

```
Phase 3: 自适应规则引擎 (独立，无依赖)
  → praxis/engine/adaptive_rules.py
  → praxis/tools/adaptive.py
  → tests/test_adaptive.py
  → 预估: 2-3h

Phase 5: 长期记忆 (独立，无依赖)
  → praxis/engine/evolution_memory.py
  → praxis/tools/memory.py
  → 修改 auto_evolve_tool 集成记忆
  → tests/test_evolution_memory.py
  → 预估: 2h

Phase 4: 多 Agent 协作 (依赖 Phase 5 的记忆存储)
  → 扩展 ai_tracker.py
  → praxis/engine/consensus.py
  → praxis/tools/agent_tracker.py
  → tests/test_consensus.py
  → 预估: 2-3h

总计: 6-8h (可分 2-3 个 session 完成)
```

---

## 八、风险与约束

| 风险 | 缓解措施 |
|:---|:---|
| 规则学习产生错误建议 | 所有规则必须经 prompt_scanner 安全扫描 + 人工审批 |
| 多 Agent 共识延迟 | 共识检查为只读操作，不阻塞交易流程 |
| 记忆存储无限增长 | 限制单文件 ≤ 1000 条，超出自动归档 |
| 进化触发导致性能问题 | 触发器异步执行，不阻塞主流程 |
| 规则冲突 | 规则优先级排序 + 互斥检测 |

---

## 九、成功标准

| 指标 | 目标 | 验证方式 |
|:---|:---:|:---|
| 规则学习覆盖率 | ≥ 3 条有效规则 | 学习后检查 learned_rules.md |
| Agent 准确率可追踪 | 支持 ≥ 2 个 Agent | record + evaluate 测试通过 |
| 进化记忆可查询 | 时间线自动生成 | generate_timeline 输出正确 |
| 零人工干预触发 | auto_evolve 自动执行 | 交易后自动评估 |
| 安全扫描 100% 覆盖 | 所有规则经 scanner | 无 scanner bypass |
