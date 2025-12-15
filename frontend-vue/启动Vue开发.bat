@echo off
chcp 65001 >nul
echo ========================================
echo    Vue前端开发服务器启动脚本
echo ========================================
echo.

REM 检查Node.js是否安装
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到Node.js！
    echo.
    echo 请先安装Node.js：
    echo 1. 访问 https://nodejs.org/
    echo 2. 下载并安装 LTS 版本
    echo 3. 重新运行此脚本
    echo.
    pause
    exit /b 1
)

echo [✓] Node.js版本：
node -v
echo.

REM 检查依赖是否已安装
if not exist "node_modules\" (
    echo [提示] 首次运行，正在安装依赖...
    echo 这可能需要几分钟，请耐心等待...
    echo.
    npm install
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败！
        pause
        exit /b 1
    )
    echo.
    echo [✓] 依赖安装完成！
    echo.
)

echo [启动] Vue开发服务器启动中...
echo.
echo ========================================
echo  服务器启动后：
echo  - 按 Ctrl + 点击下方链接打开浏览器
echo  - 或手动访问 http://localhost:5173/
echo  - 按 Ctrl + C 停止服务器
echo ========================================
echo.

npm run dev

