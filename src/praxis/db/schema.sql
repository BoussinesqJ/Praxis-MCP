-- PRAXIS SQLite Schema v1.0
-- 创建时间: 2026-07-10
-- 版本: v1.0
--
-- 变更日志:
--   v1.0 (2026-07-10) — 初始版本: 7 张核心表
--     - guardrail_state / guardrail_history (Phase 2 Guardrail)
--     - decisions / transactions (Phase 3 数据迁移)
--     - nav_history / sentinel_snapshots / audit_log (运营数据)
--
-- 设计原则:
--   1. 每张表包含 extra_data TEXT (JSON blob) 扩展字段
--   2. 每张表包含 version 字段支持后续 migration
--   3. 高频查询字段 (symbol/date/status) 有索引
--   4. 外键约束在应用层管理（SQLite 性能考虑）

-- ═══════════════════════════════════════════════════════════════════
-- Phase 2: Guardrail 纪律锁
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS guardrail_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    state TEXT NOT NULL DEFAULT 'UNINITIALIZED'
        CHECK (state IN ('UNINITIALIZED', 'LOCKED', 'ACTIVE', 'AUDITING')),
    updated_at TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT 'system',
    version INTEGER NOT NULL DEFAULT 1,
    extra_data TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS guardrail_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER NOT NULL DEFAULT 1,
    extra_data TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_guardrail_history_ts
    ON guardrail_history(created_at);

CREATE INDEX IF NOT EXISTS idx_guardrail_history_state
    ON guardrail_history(from_state, to_state);

-- ═══════════════════════════════════════════════════════════════════
-- Phase 3: 数据迁移 (JSONL → SQLite)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    investor_id TEXT NOT NULL DEFAULT '',
    portfolio_id TEXT NOT NULL DEFAULT '',
    ticker TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('buy', 'sell', 'hold', 'watch')),
    confidence REAL NOT NULL DEFAULT 0.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    reasoning TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'pending', 'approved', 'rejected', 'executed', 'reviewed', 'expired')),
    team_signals TEXT DEFAULT '[]',
    tx_id TEXT DEFAULT '',
    review_result TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER NOT NULL DEFAULT 1,
    extra_data TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_decisions_ticker ON decisions(ticker);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_investor ON decisions(investor_id, portfolio_id);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);

CREATE TABLE IF NOT EXISTS transactions (
    tx_id TEXT PRIMARY KEY,
    investor_id TEXT NOT NULL DEFAULT '',
    portfolio_id TEXT NOT NULL DEFAULT '',
    ticker TEXT NOT NULL,
    tx_type TEXT NOT NULL CHECK (tx_type IN ('buy', 'sell', 'subscribe', 'redeem', 'dividend', 'reverse')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL CHECK (price > 0),
    fee REAL NOT NULL DEFAULT 0.0 CHECK (fee >= 0),
    asset_type TEXT NOT NULL DEFAULT 'stock'
        CHECK (asset_type IN ('stock', 'etf', 'offshore_fund', 'bond', 'cash')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'reversed')),
    idempotency_key TEXT NOT NULL DEFAULT '',
    tags TEXT DEFAULT '[]',
    decision_id TEXT DEFAULT '',
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER NOT NULL DEFAULT 1,
    extra_data TEXT DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_idempotency
    ON transactions(idempotency_key) WHERE idempotency_key != '';

CREATE INDEX IF NOT EXISTS idx_transactions_ticker ON transactions(ticker);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(tx_type);
CREATE INDEX IF NOT EXISTS idx_transactions_investor ON transactions(investor_id, portfolio_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_decision ON transactions(decision_id);

CREATE TABLE IF NOT EXISTS nav_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id TEXT NOT NULL,
    portfolio_id TEXT NOT NULL,
    date TEXT NOT NULL,
    nav REAL NOT NULL,
    total_assets REAL NOT NULL,
    positions_value REAL NOT NULL,
    cash REAL NOT NULL,
    benchmark_nav REAL,
    benchmark_code TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER NOT NULL DEFAULT 1,
    extra_data TEXT DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_nav_unique
    ON nav_history(investor_id, portfolio_id, date);

CREATE INDEX IF NOT EXISTS idx_nav_investor ON nav_history(investor_id, portfolio_id);
CREATE INDEX IF NOT EXISTS idx_nav_date ON nav_history(date);

CREATE TABLE IF NOT EXISTS sentinel_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_time TEXT NOT NULL,
    signals TEXT NOT NULL DEFAULT '[]',
    overall_signal TEXT NOT NULL DEFAULT 'neutral',
    attack_defense TEXT NOT NULL DEFAULT 'defense',
    rule23_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER NOT NULL DEFAULT 1,
    extra_data TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sentinel_scan_time ON sentinel_snapshots(scan_time);
CREATE INDEX IF NOT EXISTS idx_sentinel_signal ON sentinel_snapshots(overall_signal);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL
        CHECK (event_type IN ('trade', 'decision', 'constraint', 'state_change', 'config_change', 'error', 'guardrail')),
    actor TEXT NOT NULL DEFAULT 'system',
    target TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER NOT NULL DEFAULT 1,
    extra_data TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

-- ═══════════════════════════════════════════════════════════════════
-- Phase 4 (预留): 向量库与长期记忆
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ledger_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id TEXT NOT NULL UNIQUE,
    entry_type TEXT NOT NULL DEFAULT 'transaction'
        CHECK (entry_type IN ('transaction', 'note', 'signal', 'memory')),
    content TEXT NOT NULL DEFAULT '{}',
    tags TEXT DEFAULT '[]',
    embedding BLOB,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    version INTEGER NOT NULL DEFAULT 1,
    extra_data TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ledger_entry_type ON ledger_entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_ledger_entry_created ON ledger_entries(created_at);

-- ═══════════════════════════════════════════════════════════════════
-- Schema 版本管理
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL DEFAULT ''
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES ('v1.0', '初始版本: 7 张核心表 — guardrail_state/guardrail_history/decisions/transactions/nav_history/sentinel_snapshots/audit_log/ledger_entries');
