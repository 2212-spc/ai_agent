@echo off
REM AI Agent Studio - Docker 一键启动脚本
REM 适用于 Windows

chcp 65001 >nul
echo 🤖 AI Agent Studio - Docker 部署脚本
echo ======================================
echo.

REM 检查 Docker 是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未检测到 Docker，请先安装 Docker Desktop
    echo    下载地址：https://www.docker.com/get-started
    pause
    exit /b 1
)

REM 检查 Docker Compose 是否安装
docker-compose --version >nul 2>&1
if errorlevel 1 (
    docker compose version >nul 2>&1
    if errorlevel 1 (
        echo ❌ 错误：未检测到 Docker Compose
        pause
        exit /b 1
    )
)

echo ✅ Docker 环境检测通过
echo.

REM 检查 .env 文件
if not exist .env (
    echo ⚠️  未找到 .env 文件，正在创建...
    if exist .env.example (
        copy .env.example .env >nul
        echo 📝 已从 .env.example 创建 .env 文件
        echo ⚠️  请编辑 .env 文件，填入你的 DEEPSEEK_API_KEY
        echo.
        set /p edit="是否现在编辑 .env 文件？(y/n) "
        if /i "%edit%"=="y" (
            notepad .env
        ) else (
            echo 请手动编辑 .env 文件后重新运行此脚本
            pause
            exit /b 1
        )
    ) else (
        echo ❌ 错误：未找到 .env.example 模板文件
        pause
        exit /b 1
    )
)

REM 检查 API Key 是否配置
findstr /C:"sk-your-api-key-here" .env >nul
if not errorlevel 1 (
    echo ❌ 错误：.env 文件中的 DEEPSEEK_API_KEY 未配置
    echo    请编辑 .env 文件，填入你的 API Key
    echo    获取地址：https://platform.deepseek.com/
    pause
    exit /b 1
)

echo ✅ 环境变量配置完成
echo.

REM 询问启动模式
echo 请选择启动模式：
echo 1) 生产模式（后台运行，推荐）
echo 2) 开发模式（前台运行，显示日志）
echo 3) 重新构建并启动
set /p mode="请选择 [1-3]: "

if "%mode%"=="1" (
    echo 🚀 启动生产模式...
    docker-compose up -d
) else if "%mode%"=="2" (
    echo 🔧 启动开发模式...
    docker-compose up
) else if "%mode%"=="3" (
    echo 🔨 重新构建并启动...
    docker-compose up -d --build
) else (
    echo ❌ 无效选择，退出
    pause
    exit /b 1
)

REM 等待服务启动
echo.
echo ⏳ 等待服务启动...
timeout /t 5 /nobreak >nul

REM 检查服务状态
echo.
echo 📊 服务状态：
docker-compose ps

echo.
echo ✅ 部署完成！
echo.
echo 📱 访问地址：
echo    前端界面：http://localhost
echo    后端 API：http://localhost:8000/docs
echo.
echo 📝 常用命令：
echo    查看日志：docker-compose logs -f
echo    停止服务：docker-compose down
echo    重启服务：docker-compose restart
echo.
echo 🎉 祝你使用愉快！
echo.
pause

