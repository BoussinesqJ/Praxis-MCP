@echo off
REM PRAXIS Git 推送安全审查脚本 (Windows)

echo === PRAXIS 推送安全审查 ===
echo 审查时间: %date% %time%
echo.

set ERRORS=0

REM 1. 检查硬编码路径
echo 1. 检查硬编码路径...
findstr /S /I /M "C:\Users" *.json *.yaml *.py 2>nul | findstr /V ".example" | findstr /V "test" | findstr /V "__pycache__" > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ❌ 发现硬编码路径
    set /A ERRORS+=1
) else (
    echo ✅ 无硬编码路径
)

REM 2. 检查敏感信息
echo.
echo 2. 检查敏感信息...
findstr /S /I /M "api_key password secret token" *.py *.json *.yaml 2>nul | findstr /V "example" | findstr /V "test" | findstr /V "__pycache__" > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ❌ 发现敏感信息
    set /A ERRORS+=1
) else (
    echo ✅ 无敏感信息
)

REM 3. 检查 .gitignore
echo.
echo 3. 检查 .gitignore...
if exist ".gitignore" (
    echo ✅ .gitignore 存在
) else (
    echo ❌ .gitignore 不存在
    set /A ERRORS+=1
)

REM 4. 检查配置文件
echo.
echo 4. 检查配置文件...
dir /B config\*.json 2>nul | findstr /V ".example" > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ❌ 发现实际配置文件（应使用 .example.json）
    set /A ERRORS+=1
) else (
    echo ✅ 配置文件正确
)

REM 5. 检查大文件
echo.
echo 5. 检查大文件...
for /F "delims=" %%i in ('dir /S /B /A:-D 2^>nul ^| findstr /V ".git"') do (
    for %%A in ("%%i") do (
        if %%~zA GTR 1048576 (
            echo ⚠️ 发现大文件: %%i
        )
    )
)
echo ✅ 检查完成

REM 总结
echo.
echo === 审查总结 ===
if %ERRORS% EQU 0 (
    echo ✅ 审查通过，可以推送
    exit /B 0
) else (
    echo ❌ 审查失败，发现 %ERRORS% 个问题，请修复后重新审查
    exit /B 1
)
