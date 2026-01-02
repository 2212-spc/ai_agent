# 🚀 快速开始指南

## 方式一：Docker 部署（推荐）⭐

### 前置要求
- [Docker Desktop](https://www.docker.com/get-started) 已安装并运行
- DeepSeek API Key（[获取地址](https://platform.deepseek.com/)）

### 3 步启动

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd ai_agent

# 2. 创建 .env 文件并填入 API Key
# Windows:
copy .env.example .env
# Linux/Mac:
cp .env.example .env

# 编辑 .env 文件，将 DEEPSEEK_API_KEY 改为你的真实 API Key

# 3. 一键启动
# Windows:
start.bat

# Linux/Mac:
chmod +x start.sh
./start.sh
```

### 访问应用
- 前端：http://localhost
- 后端 API：http://localhost:8000/docs

---

## 方式二：本地开发部署

### 前置要求
- Python 3.10+
- Node.js 18+
- DeepSeek API Key

### 启动后端

```bash
# 1. 进入后端目录
cd backend

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置环境变量
# Windows PowerShell:
$env:DEEPSEEK_API_KEY = "sk-your-api-key-here"

# Linux/Mac:
export DEEPSEEK_API_KEY="sk-your-api-key-here"

# 4. 启动服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 启动前端

```bash
# 1. 进入前端目录
cd frontend-vue

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
```

### 访问应用
- 前端：http://localhost:5173
- 后端 API：http://localhost:8000/docs

---

## ⚠️ 常见问题

### Docker 构建失败？
- 确保 Docker Desktop 已启动
- 检查网络连接（已配置国内镜像源，无需梯子）
- 查看日志：`docker-compose logs`

### 首次安装很慢？
- 正常现象，需要下载嵌入模型（约 500MB）
- Docker 构建需要 5-10 分钟
- 请耐心等待

### API Key 在哪里获取？
- 访问：https://platform.deepseek.com/
- 注册账号后获取 API Key
- 格式：`sk-xxxxxxxxxxxxx`

---

## 📚 更多文档

- [完整 README](README.md)
- [Docker 部署指南](DOCKER_DEPLOYMENT.md)
- [使用指南](frontend-vue/USAGE_GUIDE.md)

