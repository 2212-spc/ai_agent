# ========================================
# 🤖 AI Agent 服务器启动脚本
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   🤖 AI Agent 服务器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 清理旧进程
Write-Host "🔍 检查端口占用..." -ForegroundColor Yellow

$processes = netstat -ano | findstr :8000 | ForEach-Object {
    if ($_ -match '(\d+)$') {
        $matches[1]
    }
} | Select-Object -Unique

if ($processes) {
    Write-Host "⚠️  发现旧进程，正在清理..." -ForegroundColor Yellow
    foreach ($pid in $processes) {
        try {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "   ✅ 已停止进程 $pid" -ForegroundColor Green
        } catch {
            Write-Host "   ⚠️  进程 $pid 可能已停止" -ForegroundColor Gray
        }
    }
    Start-Sleep -Seconds 2
    Write-Host ""
} else {
    Write-Host "✅ 端口 8000 未被占用" -ForegroundColor Green
    Write-Host ""
}

# 2. 切换目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
Write-Host "📁 工作目录: $scriptDir" -ForegroundColor Cyan
Write-Host ""

# 3. 激活环境
Write-Host "📦 激活 ai-agent 环境..." -ForegroundColor Yellow
conda activate ai-agent
Write-Host ""

# 4. 显示功能
Write-Host "✨ 核心功能：" -ForegroundColor Green
Write-Host "   💬 智能对话 (DeepSeek API)" -ForegroundColor White
Write-Host "   📚 RAG 知识库 (ChromaDB + Sentence-Transformers)" -ForegroundColor White
Write-Host "   🔧 工具调用 (内置工具 + HTTP 工具)" -ForegroundColor White
Write-Host "   🌐 上网搜索 (DuckDuckGo + Jina Reader)" -ForegroundColor White
Write-Host "   📊 数学公式 (KaTeX)" -ForegroundColor White
Write-Host ""

# 5. 启动服务器
Write-Host "🚀 启动服务器..." -ForegroundColor Yellow
Write-Host "   📍 地址: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "   📖 文档: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 启动 uvicorn
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

