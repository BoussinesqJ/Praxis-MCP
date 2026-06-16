#!/bin/bash
# PRAXIS 项目 Git 初始化和上传脚本

echo "=== PRAXIS Git 初始化 ==="

# 1. 初始化 Git 仓库
echo "1. 初始化 Git 仓库..."
git init

# 2. 添加所有文件
echo "2. 添加文件..."
git add .

# 3. 检查状态
echo "3. 检查状态..."
git status

# 4. 创建初始提交
echo "4. 创建初始提交..."
git commit -m "feat: PRAXIS V2.1 - 投研纪律系统初始版本

- 53 个 MCP 工具
- 17 个 CLI 命令
- 329 个测试用例
- 完整的文档体系
- 支持 Claude Desktop/OpenCode/Tare/WorkBuddy/牛马AI 接入"

# 5. 添加远程仓库（需要替换为你的仓库地址）
echo "5. 添加远程仓库..."
echo "请执行以下命令添加远程仓库："
echo "git remote add origin <your-private-repo-url>"
echo ""
echo "6. 推送到远程仓库："
echo "git push -u origin main"

echo ""
echo "=== 完成 ==="
