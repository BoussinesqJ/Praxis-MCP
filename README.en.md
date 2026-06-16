# Praxis — Practice, Reflection, And eXponential Improvement System

> An MCP-powered investment research discipline system.  
> 30+ atomic tools for market data, portfolio management, sentiment analysis, and performance review.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io/)
[![v4.0.0](https://img.shields.io/badge/version-v4.0.0-blue.svg)](#)

---

## Overview

Praxis is an **investment research discipline system** that enforces systematic trading rules through a set of modular MCP (Model Context Protocol) tools. It connects with any MCP-compatible AI client (Claude Desktop, Claude Code, Trae, Workbuddy, OpenCode, Codex, etc.) to provide:

- **Market Data** — Real-time quotes, historical K-lines, index benchmarks, fund NAVs
- **Portfolio Management** — Holdings tracking, position sizing, constraint checking, ledger
- **Sentiment Analysis** — News aggregation, keyword sentiment, polarity scoring
- **Performance Review** — P&L attribution, discipline cost tracking, evolution engine
- **Risk Control** — Sentinel radar, stop-loss monitoring, cash floor enforcement

---

## Quick Start

```bash
pip install -e .
praxis --help
```

Full guide: [QUICKSTART.md](QUICKSTART.md) (Chinese)

---

## AI Agent Integration

Praxis communicates via the MCP protocol. To use it with your AI client, configure `.mcp.json` at project root:

```json
{
  "mcpServers": {
    "praxis": {
      "command": "python",
      "args": ["praxis/mcp_server.py"],
      "env": {
        "PRAXIS_WORKSPACE": ".",
        "PRAXIS_TOOLS_TIER": "core"
      }
    }
  }
}
```

See [AI_INTEGRATION.md](AI_INTEGRATION.md) for client-specific instructions.

### Supported Clients

| Client | Config |
|---|---|
| Claude Desktop | `.mcp.json` |
| Claude Code | `.mcp.json` (auto-detected) |
| Trae | `config/trae_config.example.json` |
| Workbuddy | `config/workbuddy_config.example.json` |
| OpenCode | `config/opencode_config.example.json` |
| Codex | Settings → MCP Server |
| Niuma AI / TARE | Config examples in `config/` |

---

## Architecture

```
praxis/
├── praxis/           # Core engine + MCP server + 30+ tools
├── praxis_sdk/       # Developer SDK
├── providers/        # Data source plugins (15 providers)
├── scripts/          # Utility scripts
├── strategies/       # Strategy templates
├── obsidian/         # System architecture docs (Obsidian-ready)
├── tpl/              # First-run templates
└── tests/            # Test suite (600+ tests)
```

### Safety Rules

- **Rule 1**: ETF grid triggers have absolute priority
- **Rule 7**: Price-target reach permits execution
- **Rule 10**: -5% hard stop-loss — unconditional
- **Circuit Breaker**: 3 failures → 60s half-open → self-healing

---

## Documentation

| Document | Language | Description |
|---|---|---|
| [QUICKSTART.md](QUICKSTART.md) | 中文 | 5-minute setup guide |
| [AI_INTEGRATION.md](AI_INTEGRATION.md) | 中文 | AI client configuration |
| [AGENTS.md](AGENTS.md) | 中文 | Architecture & conventions |
| `obsidian/11-MCP工具清单.md` | 中文 | Complete tool reference |
| [CHANGELOG.md](CHANGELOG.md) | 中文 | Version history |

---

## License

MIT License — see [LICENSE](LICENSE).

Copyright (c) 2026 BoussinesqJ
