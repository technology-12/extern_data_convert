@echo off
echo **********************************************
echo   Struct Converter Toolkit - 低代码平台
echo **********************************************
echo.
echo 正在启动 Streamlit 应用...
echo.

REM Check if streamlit is installed
python -c "import streamlit" 2>nul
if %errorlevel% neq 0 (
    echo 正在安装依赖...
    pip install streamlit pandas openpyxl
    echo.
)

echo 启动中，浏览器将自动打开...
echo 按 Ctrl+C 可停止服务
echo.
python -m streamlit run app.py --server.port 8501
pause
