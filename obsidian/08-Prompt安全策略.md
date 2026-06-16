# Prompt 安全策略

> 四层结构 + 安全扫描 + 变更审批

---

## 四层结构

```
teams/
├── base/                    # 基础层（不可自动修改）
│   ├── system_role.md       # 系统角色
│   ├── safety_guards.md     # 安全守则
│   └── tool_policy.md       # 工具权限
├── strategy/                # 策略层
│   └── grid_value.md
├── investor/                # 投资者层
│   └── demo.md
└── adaptive/                # 自适应层（可提出变更，需审批）
    └── learned_rules.md
```

---

## 权限矩阵

| 层级 | 读取 | 修改 | 审批 |
|:----:|:----:|:----:|:----:|
| base | ✅ | ❌ | ❌ |
| strategy | ✅ | 需审批 | 人工 |
| investor | ✅ | 需审批 | 人工 |
| adaptive | ✅ | 需审批 | 人工 |

---

## 危险模式检测

```python
DANGEROUS_PATTERNS = [
    r"忽略.*安全.*规则",      # critical
    r"可以.*忽略.*风控",      # critical
    r"自动.*审批",            # high
    r"不需要.*人工.*确认",    # high
    r"降低.*底线",            # medium
]
```

---

## 变更流程

```
提议变更
    ↓
安全扫描（检测危险模式）
    ↓
记录变更（append-only）
    ↓
人工审批
    ↓
执行修改
```

---

## 实现

- 扫描器：`praxis/engine/prompt_scanner.py`
- 记录器：`praxis/engine/prompt_change_recorder.py`
- 模型：`praxis/core/models/prompt_change.py`

---

## 相关链接

- [[进化引擎设计]] — Prompt 进化
- [[规则分级体系]] — 规则安全
- [[写操作安全]] — 审计日志

---

#Prompt安全 #安全机制 #四层结构

---
> **v3.0 更新说明**：本文档描述的核心设计在 v3.0 中保持稳定。v3.0 新增的断点续传、模型分级、结构化输出等模块详见 [[00-系统全景]]。

#v3.0
