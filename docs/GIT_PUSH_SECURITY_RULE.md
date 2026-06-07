# PRAXIS Git 推送安全审查规则

> **强制规则**：每次上传推送 GitHub 前必须执行安全审查，并获得用户确认

---

## 一、审查流程

```
1. 执行安全扫描
    ↓
2. 生成审查报告
    ↓
3. 用户确认
    ↓
4. 执行推送
```

---

## 二、审查清单

### 2.1 敏感信息检查

| 检查项 | 说明 | 状态 |
|--------|------|:----:|
| 硬编码路径 | 检查是否包含本地物理路径 | ⬜ |
| API Key | 检查是否包含 API 密钥 | ⬜ |
| 密码 | 检查是否包含密码 | ⬜ |
| Token | 检查是否包含访问令牌 | ⬜ |
| 私钥 | 检查是否包含私钥文件 | ⬜ |
| 个人信息 | 检查是否包含敏感个人信息 | ⬜ |

### 2.2 文件检查

| 检查项 | 说明 | 状态 |
|--------|------|:----:|
| .gitignore | 确认忽略规则正确 | ⬜ |
| 配置文件 | 确认使用模板而非实际配置 | ⬜ |
| 缓存文件 | 确认不包含缓存文件 | ⬜ |
| 临时文件 | 确认不包含临时文件 | ⬜ |
| 大文件 | 确认不包含超大文件 | ⬜ |

### 2.3 数据检查

| 检查项 | 说明 | 状态 |
|--------|------|:----:|
| 交易数据 | 确认交易数据可公开 | ⬜ |
| 决策记录 | 确认决策记录可公开 | ⬜ |
| 审计日志 | 确认审计日志可公开 | ⬜ |
| 行情缓存 | 确认不包含行情缓存 | ⬜ |

---

## 三、审查脚本

### 3.1 自动扫描脚本

```bash
#!/bin/bash
# scripts/security_check.sh

echo "=== PRAXIS 安全审查 ==="

# 1. 检查硬编码路径
echo "1. 检查硬编码路径..."
HARDCODED_PATHS=$(grep -r "C:/Users" --include="*.json" --include="*.yaml" --include="*.py" . 2>/dev/null | grep -v ".example" | grep -v "test" | grep -v "__pycache__")
if [ -n "$HARDCODED_PATHS" ]; then
    echo "❌ 发现硬编码路径："
    echo "$HARDCODED_PATHS"
    exit 1
else
    echo "✅ 无硬编码路径"
fi

# 2. 检查敏感信息
echo "2. 检查敏感信息..."
SENSITIVE=$(grep -r "api_key\|password\|secret\|token" --include="*.py" --include="*.json" --include="*.yaml" . 2>/dev/null | grep -v "example" | grep -v "test" | grep -v "__pycache__" | grep -v ".git")
if [ -n "$SENSITIVE" ]; then
    echo "❌ 发现敏感信息："
    echo "$SENSITIVE"
    exit 1
else
    echo "✅ 无敏感信息"
fi

# 3. 检查 .gitignore
echo "3. 检查 .gitignore..."
if [ -f ".gitignore" ]; then
    echo "✅ .gitignore 存在"
else
    echo "❌ .gitignore 不存在"
    exit 1
fi

# 4. 检查配置文件
echo "4. 检查配置文件..."
CONFIG_FILES=$(find config -name "*.json" -not -name "*.example.json" 2>/dev/null)
if [ -n "$CONFIG_FILES" ]; then
    echo "❌ 发现实际配置文件（应使用 .example.json）："
    echo "$CONFIG_FILES"
    exit 1
else
    echo "✅ 配置文件正确"
fi

# 5. 检查大文件
echo "5. 检查大文件..."
LARGE_FILES=$(find . -type f -size +1M -not -path "./.git/*" 2>/dev/null)
if [ -n "$LARGE_FILES" ]; then
    echo "⚠️ 发现大文件："
    echo "$LARGE_FILES"
else
    echo "✅ 无大文件"
fi

echo ""
echo "=== 审查完成 ==="
echo "请确认以上检查结果后执行推送"
```

---

## 四、审查报告模板

```
=== PRAXIS 推送安全审查报告 ===

审查时间：YYYY-MM-DD HH:MM:SS
审查人：Reasonix
推送目标：https://github.com/your-username/Praxis.git

【审查结果】
- 硬编码路径：✅ 通过
- 敏感信息：✅ 通过
- 配置文件：✅ 通过
- 大文件：✅ 通过

【变更摘要】
- 新增文件：X 个
- 修改文件：X 个
- 删除文件：X 个

【用户确认】
请确认是否继续推送？
```

---

## 五、执行规则

### 5.1 强制规则

1. **每次推送前必须执行安全审查**
2. **审查报告必须展示给用户**
3. **必须获得用户明确确认后才能推送**
4. **任何审查失败必须修复后重新审查**

### 5.2 例外情况

以下情况可以跳过审查：
- 紧急修复（需记录原因）
- 文档更新（无代码变更）

### 5.3 审查记录

每次审查结果记录到：

```
data/audit/git_push_audit.jsonl
```

格式：
```json
{
  "timestamp": "2026-06-04T20:35:00+08:00",
  "commit_hash": "abc123",
  "review_result": "passed",
  "checks": {
    "hardcoded_paths": "passed",
    "sensitive_info": "passed",
    "config_files": "passed",
    "large_files": "passed"
  },
  "approved_by": "用户"
}
```

---

## 六、快速命令

```bash
# 执行安全审查
scripts/security_check.sh

# Windows
scripts\security_check.bat
```

---

**此规则强制执行，每次推送前必须审查并获得确认！**
