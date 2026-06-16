#!/bin/bash
# PRAXIS Git 推送安全审查脚本

echo "=== PRAXIS 推送安全审查 ==="
echo "审查时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

ERRORS=0

# 1. 检查硬编码路径
echo "1. 检查硬编码路径..."
HARDCODED_PATHS=$(grep -r "C:/Users\|C:\\Users\|/Users/" --include="*.json" --include="*.yaml" --include="*.py" --include="*.md" . 2>/dev/null | grep -v ".example" | grep -v "test" | grep -v "__pycache__" | grep -v ".git/" | grep -v "GIT_PUSH_SECURITY_RULE.md" | grep -v "DEVELOPMENT_SUMMARY.md")
if [ -n "$HARDCODED_PATHS" ]; then
    echo "❌ 发现硬编码路径："
    echo "$HARDCODED_PATHS"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ 无硬编码路径"
fi

# 2. 检查 API Key / 密码 / Token
echo ""
echo "2. 检查敏感信息..."
SENSITIVE=$(grep -ri "api_key\|password\|secret\|token\|private_key" --include="*.py" --include="*.json" --include="*.yaml" . 2>/dev/null | grep -v "example" | grep -v "test" | grep -v "__pycache__" | grep -v ".git/" | grep -v "node_modules")
if [ -n "$SENSITIVE" ]; then
    echo "❌ 发现敏感信息："
    echo "$SENSITIVE"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ 无敏感信息"
fi

# 3. 检查 .gitignore
echo ""
echo "3. 检查 .gitignore..."
if [ -f ".gitignore" ]; then
    echo "✅ .gitignore 存在"
else
    echo "❌ .gitignore 不存在"
    ERRORS=$((ERRORS + 1))
fi

# 4. 检查实际配置文件
echo ""
echo "4. 检查配置文件..."
CONFIG_FILES=$(find config -name "*.json" -not -name "*.example.json" 2>/dev/null)
if [ -n "$CONFIG_FILES" ]; then
    echo "❌ 发现实际配置文件（应使用 .example.json）："
    echo "$CONFIG_FILES"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ 配置文件正确"
fi

# 5. 检查大文件
echo ""
echo "5. 检查大文件..."
LARGE_FILES=$(find . -type f -size +1M -not -path "./.git/*" -not -path "./__pycache__/*" -not -path "./.pytest_cache/*" 2>/dev/null)
if [ -n "$LARGE_FILES" ]; then
    echo "⚠️ 发现大文件："
    echo "$LARGE_FILES"
else
    echo "✅ 无大文件"
fi

# 6. 检查 __pycache__ 目录
echo ""
echo "6. 检查缓存目录..."
CACHE_DIRS=$(find . -type d -name "__pycache__" -not -path "./.git/*" 2>/dev/null)
if [ -n "$CACHE_DIRS" ]; then
    echo "⚠️ 发现缓存目录（建议清理）："
    echo "$CACHE_DIRS"
else
    echo "✅ 无缓存目录"
fi

# 总结
echo ""
echo "=== 审查总结 ==="
if [ $ERRORS -eq 0 ]; then
    echo "✅ 审查通过，可以推送"
    exit 0
else
    echo "❌ 审查失败，发现 $ERRORS 个问题，请修复后重新审查"
    exit 1
fi
