@echo off
REM PRAXIS 项目 Git 初始化和上传脚本 (Windows)

echo === PRAXIS Git 初始化 ===

REM 1. 初始化 Git 仓库
echo 1. 初始化 Git 仓库...
git init

REM 2. 添加所有文件
echo 2. 添加文件...
git add .

REM 3. 检查状态
echo 3. 检查状态...
git status

REM 4. 创建初始提交
echo 4. 创建初始提交...
git commit -m "feat: PRAXIS V2.1 - 投研纪律系统初始版本"

REM 5. 提示用户添加远程仓库
echo 5. 添加远程仓库...
echo 请执行以下命令添加远程仓库：
echo git remote add origin ^<your-private-repo-url^>
echo.
echo 6. 推送到远程仓库：
echo git push -u origin main

echo.
echo === 完成 ===
pause
