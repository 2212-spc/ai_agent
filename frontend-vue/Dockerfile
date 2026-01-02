# 前端 Dockerfile - Vue 3 Frontend
# 使用国内镜像源（无需梯子）
FROM registry.cn-hangzhou.aliyuncs.com/acs/node:18-alpine as builder

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖（使用国内镜像加速）
RUN npm config set registry https://registry.npmmirror.com && \
    npm install

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# 生产环境 - 使用 nginx 提供静态文件
# 使用国内镜像源（无需梯子）
FROM registry.cn-hangzhou.aliyuncs.com/acs/nginx:alpine

# 复制构建产物到 nginx
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]

