@echo off
chcp 65001 > nul
title Qwen3-TTS WebUI

echo ========================================
echo    Qwen3-TTS 语音合成系统启动器
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] 检查 Node.js 环境...
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js
    pause
    exit /b 1
)
echo [OK] Node.js 已安装

echo.
echo [2/3] 检查依赖...
if not exist "node_modules" (
    echo [INFO] 正在安装依赖...
    call npm install
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)
echo [OK] 依赖已就绪

echo.
echo [3/3] 检查 Python 环境...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [警告] 未找到 Python，部分功能可能无法使用
) else (
    echo [OK] Python 已安装
    python --version
)

echo.
echo ========================================
echo    启动服务中...
echo ========================================
echo.
echo 访问地址: http://localhost:3000
echo 按 Ctrl+C 停止服务
echo.

npm start
