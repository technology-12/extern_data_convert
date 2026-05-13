@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   Extern 变量映射工具
echo ============================================
echo.
python extern_mapper_gui.py
if errorlevel 1 (
    echo.
    echo 运行出错！请确保已安装 Python 3.7+
    pause
)
