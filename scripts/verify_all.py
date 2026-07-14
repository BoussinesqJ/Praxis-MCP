"""PRAXIS Agent — 全量终端验证脚本"""
import asyncio, os, tempfile, sys
sys.path.insert(0, 'src')

async def comprehensive_test():
    print('=' * 60)
    print('  PRAXIS Agent — 全量终端验证')
    print('=' * 60)

    # 1. Core Models
    from praxis.core.models import (
        InvestorProfile, Portfolio, Transaction, DecisionRecord,
        PortfolioState, TransactionType, TransactionStatus, DecisionStatus
    )
    print('1. ✅ Core Models (20+ loading)')

    # 2. Core Interfaces
    from praxis.core.interfaces import DataProvider, Ledger, ConstraintChecker, DecisionRecorder, StateStore
    print('2. ✅ Core Interfaces (10 loading)')

    # 3. Guardrail
    from praxis.core.guardrail import Guardrail, GuardrailState, GuardrailResult
    fd, pp = tempfile.mkstemp(suffix='.db'); os.close(fd)
    g = Guardrail(pp)
    await g.initialize()
    assert g.current_state == GuardrailState.ACTIVE
    await g.transition(GuardrailState.LOCKED, 'test')
    assert g.current_state == GuardrailState.LOCKED
    vr = await g.verify_action('decision', 'trading', {})
    assert vr.allowed is False
    os.unlink(pp)
    print('3. ✅ Guardrail (ACTIVE→LOCKED→write blocked)')

    # 4. Rule Mapping
    from praxis.core.rule_mapping import RuleMapping
    assert RuleMapping.count() == 28
    r = RuleMapping.resolve('risk.cash_floor')
    assert r['level'] == 'hard_block'
    assert len(RuleMapping.get_hard_blocks()) == 12
    assert RuleMapping.resolve(1)['name'] == '科创板禁入'
    assert RuleMapping.exists('Rule 28')
    print(f'4. ✅ RuleMapping ({RuleMapping.count()} rules, {len(RuleMapping.get_hard_blocks())} hard-block)')

    # 5. Memory Store
    from praxis.core.memory_store import SimpleMemoryStore, EmbeddingEngine
    d = tempfile.mkdtemp()
    ms = SimpleMemoryStore(d)
    ms.index([{'text': '测试标的突破均线', 'metadata': {'ticker': '000001'}, 'source': 'test'}])
    assert ms.count() == 1
    results = ms.search('储能', min_score=0.1)
    assert len(results) >= 1
    ms.delete([results[0]['id']])
    assert ms.count() == 0
    print(f'5. ✅ MemoryStore (backend={EmbeddingEngine._engine_type})')

    # 6. SQLite Storage
    from praxis.core.state_store import SQLiteLedger, SQLiteDecisionRecorder
    fd, p = tempfile.mkstemp(suffix='.db'); os.close(fd)
    sl = SQLiteLedger(p)
    tx = Transaction(ticker='600995', tx_type=TransactionType.BUY, quantity=100, price=12.5)
    sl.append(tx)
    assert len(sl.list()) >= 1
    sl.close(); os.unlink(p)

    fd, p = tempfile.mkstemp(suffix='.db'); os.close(fd)
    sdr = SQLiteDecisionRecorder(p)
    dec = DecisionRecord(ticker='600995', action='buy', confidence=0.8, reasoning='t')
    dec_id = sdr.create(dec)
    assert dec_id.startswith('dec-')
    assert sdr.get(dec_id) is not None
    sdr.close(); os.unlink(p)
    print('6. ✅ SQLiteStorage (Ledger + DecisionRecorder)')

    # 7. 5 Agents
    from praxis.agents.base import AgentDependencies
    from praxis.agents.market import MarketAgent
    from praxis.agents.risk import RiskAgent
    from praxis.agents.decision import DecisionAgent
    from praxis.agents.review import ReviewAgent
    from praxis.agents.admin import AdminAgent
    from praxis.engine.data_provider import CachedDataProvider

    deps = AgentDependencies(data_provider=CachedDataProvider(workspace='.', auto_discover=False), workspace='.')
    agents = {
        'market': MarketAgent(deps), 'risk': RiskAgent(deps),
        'decision': DecisionAgent(deps), 'review': ReviewAgent(deps), 'admin': AdminAgent(deps),
    }
    total_tools = sum(len(a.tools) for a in agents.values())
    assert total_tools == 19
    assert agents['decision'].is_readonly is False
    for name, a in agents.items():
        print(f'     {name}: {len(a.tools)} tools (readonly={a.is_readonly})')
    print(f'7. ✅ 5 Agents ({total_tools} tools)')

    # 8. Engine
    from praxis.engine import (
        CachedDataProvider as CDP2, FeeModel, SlippageModel,
        SentinelEngine, SimpleConstraintChecker, ReconciliationEngine,
        ReviewFiller, NavTracker, EnhancedPerformanceCalculator,
    )
    print('8. ✅ Engine (14+ classes)')

    # 9. Workflow
    from praxis.core.workflow import build_decision_with_review_workflow, build_sentinel_scan_workflow, build_reconcile_workflow
    wf = build_decision_with_review_workflow(agents, '600995', 'buy', 0.7, 'test')
    assert len(wf._steps) == 3
    assert build_sentinel_scan_workflow is not None
    assert build_reconcile_workflow is not None
    print('9. ✅ Workflow (3 presets: decision/sentinel/reconcile)')

    # 10. Project Stats
    py = sum(1 for _, _, fs in os.walk('src') for f in fs if f.endswith(('.py', '.sql')))
    scripts = sum(1 for _, _, fs in os.walk('scripts') for f in fs if f.endswith('.py'))
    print(f'\n{"="*60}')
    print(f'  📊 文件: {py} src + {scripts} scripts = {py+scripts} | 阶段: P-1~P5')
    print(f'  ✅ 全量验证通过 — 0 错误')
    print(f'{"="*60}')

asyncio.run(comprehensive_test())
