# 🐳 Docker 部署指南

本项目已完整支持 Docker 容器化部署，一键启动，功能完整不打折扣！

## 📋 前置要求

- [Docker](https://www.docker.com/get-started) 20.10 或更高版本
- [Docker Compose](https://docs.docker.com/compose/install/) 2.0 或更高版本
- DeepSeek API Key（[获取地址](https://platform.deepseek.com/)）

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd ai_agent
```

### 2. 配置环境变量

复制环境变量模板并填写你的 API Key：

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

编辑 `.env` 文件，填入你的 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=sk-your-api-key-here
```

### 3. 一键启动

```bash
docker-compose up -d
```

第一次启动会下载依赖和模型，大约需要 5-10 分钟，请耐心等待。

### 4. 访问应用

- **前端界面**：http://localhost
- **后端 API 文档**：http://localhost:8000/docs
- **后端健康检查**：http://localhost:8000/health

## 📦 部署架构

```
┌─────────────────────────────────────────┐
│          Docker Network                  │
│                                          │
│  ┌────────────┐      ┌────────────┐    │
│  │  Frontend  │      │  Backend   │    │
│  │  (Nginx)   │◄────►│  (FastAPI) │    │
│  │  Port: 80  │      │ Port: 8000 │    │
│  └────────────┘      └────────────┘    │
│        │                    │           │
│        │                    │           │
│        ▼                    ▼           │
│   Static Files         Data Volume     │
│   (Vue Build)         (SQLite, Chroma) │
└─────────────────────────────────────────┘
         │                      │
         ▼                      ▼
   http://localhost      http://localhost:8000
```

## 🛠️ 常用命令

### 启动服务

```bash
# 前台运行（查看日志）
docker-compose up

# 后台运行
docker-compose up -d
```

### 停止服务

```bash
docker-compose down
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs

# 查看指定服务日志
docker-compose logs backend
docker-compose logs frontend

# 实时查看日志
docker-compose logs -f
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启指定服务
docker-compose restart backend
docker-compose restart frontend
```

### 重新构建

```bash
# 重新构建并启动
docker-compose up -d --build

# 强制重建（不使用缓存）
docker-compose build --no-cache
```

### 清理容器和镜像

```bash
# 停止并删除容器
docker-compose down

# 删除容器、网络、镜像
docker-compose down --rmi all

# 删除容器、网络、卷（⚠️ 会删除数据）
docker-compose down -v
```

## 📁 数据持久化

数据会自动持久化到 `backend/data` 目录，包括：

- `agent.db` - SQLite 数据库（用户、会话、记忆等）
- `chroma/` - 向量数据库（知识库、记忆向量）
- `uploads/` - 上传的文档
- `notes/` - AI 生成的笔记
- `diagrams/` - 生成的图表

**备份数据**：

```bash
# 创建备份
tar -czf backup-$(date +%Y%m%d).tar.gz backend/data/

# 恢复备份
tar -xzf backup-20250102.tar.gz
```

## 🔧 高级配置

### 修改端口

编辑 `docker-compose.yml`：

```yaml
services:
  frontend:
    ports:
      - "8080:80"  # 修改前端端口为 8080
  
  backend:
    ports:
      - "9000:8000"  # 修改后端端口为 9000
```

### 配置资源限制

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### 使用外部 API 代理

如果你的 DeepSeek API 需要通过代理访问：

```yaml
services:
  backend:
    environment:
      - DEEPSEEK_BASE_URL=https://your-proxy.com/v1
      - HTTP_PROXY=http://your-proxy:port
      - HTTPS_PROXY=http://your-proxy:port
```

### 开发模式（热更新）

如果需要在 Docker 中进行开发，可以挂载代码目录：

```yaml
services:
  backend:
    volumes:
      - ./backend/app:/app/app  # 挂载代码目录
    command: uvicorn app.main:app --reload --host 0.0.0.0
  
  frontend:
    volumes:
      - ./frontend-vue/src:/app/src  # 挂载源代码
    command: npm run dev -- --host 0.0.0.0
```

## 🌐 生产环境部署

### 1. 使用生产配置

创建 `docker-compose.prod.yml`：

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: always
    ports:
      - "8000:8000"
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    volumes:
      - ./backend/data:/app/data
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
  
  frontend:
    build:
      context: ./frontend-vue
      dockerfile: Dockerfile
    restart: always
    ports:
      - "80:80"
    depends_on:
      - backend
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

启动生产环境：

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 2. 使用 HTTPS（推荐）

使用 Let's Encrypt + Nginx 反向代理：

```bash
# 安装 Certbot
sudo apt-get install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 配置 Nginx 反向代理到 Docker 容器
```

### 3. 性能优化

#### 后端优化

```dockerfile
# backend/Dockerfile
FROM python:3.10-slim

# 使用多阶段构建
FROM python:3.10-slim as builder
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.10-slim
COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

# 使用 Gunicorn + Uvicorn workers
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

#### 前端优化

前端已使用 Nginx + Gzip 压缩，生产构建已优化。

## 🐛 故障排查

### 1. 容器无法启动

```bash
# 查看详细日志
docker-compose logs backend

# 常见问题：
# - API Key 未配置：检查 .env 文件
# - 端口被占用：修改 docker-compose.yml 中的端口
# - 磁盘空间不足：清理 Docker 镜像
```

### 2. 前端无法访问后端

```bash
# 检查网络连接
docker-compose exec frontend ping backend

# 检查后端健康状态
curl http://localhost:8000/docs
```

### 3. 数据丢失

```bash
# 检查数据卷
docker volume ls

# 检查数据目录
ls -la backend/data/
```

### 4. 性能问题

```bash
# 查看容器资源使用
docker stats

# 查看容器进程
docker-compose top
```

## 📊 监控和日志

### 使用 Docker Compose 日志

```bash
# 查看最近 100 行日志
docker-compose logs --tail=100

# 实时查看日志
docker-compose logs -f --tail=10

# 查看特定时间的日志
docker-compose logs --since 2024-01-01 --until 2024-01-02
```

### 日志文件位置

- 后端日志：通过 `docker-compose logs backend` 查看
- Nginx 访问日志：在容器内 `/var/log/nginx/access.log`
- Nginx 错误日志：在容器内 `/var/log/nginx/error.log`

## 🔒 安全建议

1. **不要在公网暴露 8000 端口**：只通过前端 Nginx 访问
2. **使用强密码**：设置复杂的用户密码
3. **定期备份数据**：每天备份 `backend/data` 目录
4. **使用 HTTPS**：生产环境必须使用 SSL/TLS
5. **更新镜像**：定期重新构建以获取安全更新

## 🎯 部署到云平台

### 部署到 AWS ECS

```bash
# 1. 构建镜像
docker-compose build

# 2. 推送到 ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.region.amazonaws.com
docker tag ai-agent-backend:latest <account>.dkr.ecr.region.amazonaws.com/ai-agent-backend:latest
docker push <account>.dkr.ecr.region.amazonaws.com/ai-agent-backend:latest

# 3. 创建 ECS 任务定义和服务
```

### 部署到 Railway

1. 连接 GitHub 仓库
2. 选择 Dockerfile 部署
3. 设置环境变量 `DEEPSEEK_API_KEY`
4. 自动部署

### 部署到 Render

1. 创建 Web Service
2. 选择 Docker 运行时
3. 设置环境变量
4. 部署

## 💡 最佳实践

1. **使用 .env 文件**：不要在代码中硬编码敏感信息
2. **定期备份**：设置自动备份脚本
3. **监控日志**：定期检查错误日志
4. **资源限制**：在生产环境设置内存和 CPU 限制
5. **健康检查**：使用 Docker 健康检查确保服务正常

## 📞 获取帮助

如有问题，请：

1. 查看日志：`docker-compose logs`
2. 检查文档：[README.md](README.md)
3. 提交 Issue：包含日志和错误信息

---

**祝你部署顺利！🎉**

