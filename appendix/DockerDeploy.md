# 毕业设计：云服务器 + Docker 容器化部署方案 (v1)

## 1. 部署架构分析

根据您的项目代码结构，这是一个**前后端分离开发，但合一部署**的项目。
在 `app.py` 中有如下代码：

```python
app = Flask(__name__, static_folder='front-end/dist', static_url_path='')
```

这表明后端的 Flask 应用会直接接管并代理前端 Vue 编译后的静态文件。因此，我们**只需要打包出一个包含前后端所有代码的 Docker 镜像**即可，不需要单独部署 Nginx，这样可以极大简化部署流程，完美契合 "Build Once, Run Everywhere" 的理念。

***

## 2. 部署详细规划

我们采用\*\*多阶段构建（Multi-stage Build）\*\*的 Dockerfile 方案：第一阶段使用 Node.js 环境编译前端 Vue 代码；第二阶段使用 Python 环境，安装 Flask 等后端依赖，并将第一阶段编译好的前端产物复制过来。

### 阶段一：本地准备与打包 (Windows 环境)

**1. 创建必要的部署配置文件**
接下来需要在项目根目录创建以下文件（后续可由助手代劳）：

- `Dockerfile`：定义多阶段构建流程。
- `docker-compose.yml`：定义容器运行参数、端口映射和环境变量。
- `requirements.txt`：Python 后端依赖清单（如 `flask`, `flask-cors`, `cozepy`, `gunicorn`）。
- `.dockerignore`：排除不需要打包进镜像的文件（如 `node_modules`, `.git`, `.venv`）。

**2. 本地构建镜像**
在 Windows 终端（项目根目录）执行：

```bash
# 替换为您的阿里云镜像仓库地址
docker build -t registry.cn-xxx.aliyuncs.com/您的命名空间/您的仓库名:v1 .
```

**3. 推送镜像到阿里云**

```bash
# 登录阿里云镜像仓库
docker login --username=您的阿里云账号 registry.cn-xxx.aliyuncs.com
# 推送镜像
docker push registry.cn-xxx.aliyuncs.com/您的命名空间/您的仓库名:v1
```

### 阶段二：云服务器环境初始化 (Aliyun ECS)

**1. 配置安全组 (Security Group)**

- 登录阿里云控制台，进入 ECS 实例的安全组配置。
- **必须开放的端口**：`22` (SSH登录)、`80` (HTTP访问，映射到容器内的 Flask 端口)。

**2. 安装 Docker 和 Docker Compose**
SSH 登录云主机后执行安装脚本（针对国内阿里云环境优化）：

```bash
# 卸载旧版本（如果有）
sudo apt-get remove docker docker-engine docker.io containerd runc

# 更新 apt 并安装依赖包
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 添加阿里云 Docker 的 GPG 密钥
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 设置阿里云 Docker 稳定版仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 启动 Docker 并设置开机自启
sudo systemctl enable --now docker

# 验证安装
docker -v
docker compose version
```

### 阶段三：云端拉取与运行 (Aliyun ECS)

**1. 拉取代码获取运行配置**
为了拿到 `docker-compose.yml`，可以在云主机上通过 Git 从 Gitee 拉取代码：

```bash
git clone https://gitee.com/您的用户名/您的仓库.git
cd 您的仓库目录
```

**2. 拉取镜像并启动**

```bash
# 登录阿里云镜像仓库（拉取私有镜像需要）
docker login --username=您的阿里云账号 registry.cn-xxx.aliyuncs.com

# 后台启动服务
docker-compose up -d
```

***

## 3. 核心配置文件示例（待创建）

### 推荐的 Dockerfile 模板
```dockerfile
# ==================== 阶段一：前端构建 ====================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/front-end
# 利用缓存机制，先复制 package.json 安装依赖
COPY front-end/package*.json ./
RUN npm config set registry https://registry.npmmirror.com/ && npm install
# 复制所有前端代码并打包
COPY front-end/ ./
RUN npm run build

# ==================== 阶段二：后端运行 ====================
FROM python:3.10-slim
WORKDIR /app
# 设置时区和环境变量
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

# 暴露端口（Flask 默认 5000）
EXPOSE 5000

# 生产环境推荐使用 gunicorn 启动 Flask (注意：必须使用单进程，否则内存状态不同步)
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
```

### 推荐的 docker-compose.yml 模板

```yaml
version: '3.8'
services:
  web:
    image: registry.cn-xxx.aliyuncs.com/您的命名空间/您的仓库名:v1
    container_name: graduation_project_web
    ports:
      - "80:5000"  # 将云主机的 80 端口映射到容器的 5000 端口
    environment:
      # 在这里配置您的 Coze API Token 和其他环境变量
      # 推荐使用 ${COZE_API_TOKEN:-默认值} 的形式，以避免未设置环境变量时覆盖代码中的默认有效 Token
      - COZE_API_TOKEN=${COZE_API_TOKEN:-pat_Ay5MQdVJ3ZRP9q7l3YoHHb4jlTjbEhNks5cP9hatMMCkUGgzq1JeoDKPnFDz5ky9}
      - COZE_BOT_ID_100KW=7594731318777397284
    restart: always  # 崩溃或服务器重启后自动重启
```

***

## 4. 下一步行动 (Action Items)

如果您确认该方案，我们可以立即在本地 Windows 环境开始执行以下操作：

1. [ ] 在项目根目录生成 `requirements.txt`。
2. [ ] 在项目根目录生成 `.dockerignore`。
3. [ ] 结合您的阿里云实际信息，生成确切的 `Dockerfile` 和 `docker-compose.yml`。
4. [ ] 指导您在本地进行 `docker build` 并推送到阿里云。