#!/bin/bash
# AI Agent Studio - Docker 一键启动脚本
# 适用于 Linux/Mac

set -e  # 遇到错误立即退出

echo "🤖 AI Agent Studio - Docker 部署脚本"
echo "======================================"
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误：未检测到 Docker，请先安装 Docker"
    echo "   下载地址：https://www.docker.com/get-started"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ 错误：未检测到 Docker Compose，请先安装"
    echo "   参考文档：https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker 环境检测通过"
echo ""

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件，正在创建..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "📝 已从 .env.example 创建 .env 文件"
        echo "⚠️  请编辑 .env 文件，填入你的 DEEPSEEK_API_KEY"
        echo ""
        read -p "是否现在编辑 .env 文件？(y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${EDITOR:-nano} .env
        else
            echo "请手动编辑 .env 文件后重新运行此脚本"
            exit 1
        fi
    else
        echo "❌ 错误：未找到 .env.example 模板文件"
        exit 1
    fi
fi

# 检查 API Key 是否配置
if grep -q "sk-your-api-key-here" .env; then
    echo "❌ 错误：.env 文件中的 DEEPSEEK_API_KEY 未配置"
    echo "   请编辑 .env 文件，填入你的 API Key"
    echo "   获取地址：https://platform.deepseek.com/"
    exit 1
fi

echo "✅ 环境变量配置完成"
echo ""

# 询问启动模式
echo "请选择启动模式："
echo "1) 生产模式（后台运行，推荐）"
echo "2) 开发模式（前台运行，显示日志）"
echo "3) 重新构建并启动"
read -p "请选择 [1-3]: " mode

case $mode in
    1)
        echo "🚀 启动生产模式..."
        docker-compose up -d
        ;;
    2)
        echo "🔧 启动开发模式..."
        docker-compose up
        ;;
    3)
        echo "🔨 重新构建并启动..."
        docker-compose up -d --build
        ;;
    *)
        echo "❌ 无效选择，退出"
        exit 1
        ;;
esac

# 等待服务启动
echo ""
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "📊 服务状态："
docker-compose ps

echo ""
echo "✅ 部署完成！"
echo ""
echo "📱 访问地址："
echo "   前端界面：http://localhost"
echo "   后端 API：http://localhost:8000/docs"
echo ""
echo "📝 常用命令："
echo "   查看日志：docker-compose logs -f"
echo "   停止服务：docker-compose down"
echo "   重启服务：docker-compose restart"
echo ""
echo "🎉 祝你使用愉快！"

