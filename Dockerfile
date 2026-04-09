# ==================== 阶段一：前端构建 ====================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/front-end

# 配置 npm 镜像加速并安装依赖
COPY front-end/package*.json front-end/pnpm-lock.yaml* ./
RUN npm config set registry https://registry.npmmirror.com/ && \
    if [ -f pnpm-lock.yaml ]; then npm install -g pnpm && pnpm install; else npm install; fi

# 复制前端代码并打包
COPY front-end/ ./
RUN npm run build


# ==================== 阶段二：后端运行 ====================
FROM python:3.10-slim
WORKDIR /app

# 设置环境变量
ENV TZ=Asia/Shanghai \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装后端依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端代码
COPY app.py .

# 极其重要：从阶段一中把前端编译产物复制到后端预期的目录中
COPY --from=frontend-builder /app/front-end/dist /app/front-end/dist

# 暴露 Flask 端口
EXPOSE 5000

# 使用 Gunicorn 作为生产级 WSGI 服务器启动
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]