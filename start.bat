@echo off
chcp 65001 >nul
title Solo 视频生成工具

cd /d "%~dp0"

echo.
echo ============================================
echo    Solo 视频生成工具 - 一键启动
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 安装依赖
echo [1/2] 检查依赖...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [警告] 依赖安装可能有问题，继续启动...
)

:: 启动服务
echo [2/2] 启动服务...
echo.
echo 访问地址: http://127.0.0.1:5000
echo 按 Ctrl+C 停止服务
echo.

:: 自动打开浏览器
start "" http://127.0.0.1:5000
timeout /t 2 /nobreak >nul

python app.py

pause