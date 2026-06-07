#!/bin/bash
# PRAXIS V1.1 GitHub 上传脚本
# 使用前请确保已配置 GitHub SSH 或 HTTPS 认证

echo "=== PRAXIS V1.1 GitHub 上传脚本 ==="

# 1. 检查 Git 状态
echo "1. 检查 Git 状态..."
git status

# 2. 添加所有文件（排除 .gitignore 中的文件）
echo ""
echo "2. 添加文件..."
git add .

# 3. 检查将要提交的文件
echo ""
echo "3. 检查将要提交的文件..."
git status --short

# 4. 确认提交
echo ""
read -p "确认提交以上文件？(y/N): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "已取消提交"
    exit 1
fi

# 5. 创建提交
echo ""
echo "4. 创建提交..."
git commit -m "feat: PRAXIS V1.1 - MCP工具扩展与测试增强

## 主要更新
- MCP 工具扩展：40 → 53 个（新增交易摩擦、数据质量、Prompt版本工具）
- 测试覆盖增强：114 → 137 个（新增 23 个单元测试）
- 文档全面更新（README、ROADMAP、DEVELOPMENT_SUMMARY、Obsidian）
- 配置修复（strategies/grid_value.yaml）

## 新增工具
- 交易摩擦：calculate_fee, calculate_slippage, check_trading_time, get_confirm_date
- 数据质量：check_quote_quality, clean_quote_data, get_quality_report
- Prompt版本：check_prompt_safety, list_prompt_versions, get_prompt_version, create_prompt_version, rollback_prompt, get_version_diff

## 测试结果
- 137 passed in 7.88s
- 所有测试通过

## 安全改进
- Prompt 安全扫描器（15 种危险模式）
- 数据质量检查（缺失字段、异常值检测）
- 交易摩擦建模（佣金、印花税、过户费）"

# 6. 添加远程仓库（如果还没有添加）
echo ""
echo "5. 检查远程仓库..."
git remote -v

if [ -z "$(git remote -v)" ]; then
    echo "请执行以下命令添加远程仓库："
    echo "git remote add origin git@github.com:<your-username>/praxis.git"
    echo ""
    echo "然后推送到 GitHub："
    echo "git push -u origin main"
else
    echo ""
    echo "6. 推送到 GitHub..."
    git push -u origin main
fi

echo ""
echo "=== 完成 ==="
echo ""
echo "请检查 GitHub 仓库确认上传成功："
echo "https://github.com/<your-username>/praxis"
