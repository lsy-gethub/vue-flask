# 配电网规划辅助平台 - 项目配置指南

## 项目概述

本项目是一个基于 Flask + Vue3 的配电网规划辅助平台，后端采用 Flask 提供 API 服务，前端采用 Vue3 + Element Plus 构建可视化界面。

## 环境要求

| 环境 | 版本要求 |
|------|---------|
| Python | >= 3.11 |
| Node.js | ^20.19.0 或 >= 22.12.0 |
| pnpm/npm | 最新版本 |

---

## 一、后端环境配置（Flask）

### 1.1 安装 Python

确保系统已安装 Python 3.11 或更高版本：

```bash
python --version
```

### 1.2 创建虚拟环境（推荐）

```bash
cd 毕业设计

python -m venv venv

venv\Scripts\activate
```

### 1.3 安装依赖

```bash
pip install -r requirements.txt
```

依赖列表：
- `flask` - Web 框架
- `flask-cors` - 跨域支持
- `cozepy` - Coze AI SDK

### 1.4 配置环境变量

如需使用 AI 调度功能，需配置 Coze API Token：

```bash
set COZE_API_TOKEN=your_token_here
```

或在代码中直接配置（app.py）。

### 1.5 启动后端服务

```bash
python app.py
```

服务默认运行在 `http://127.0.0.1:5000`

---

## 二、前端环境配置（Vue3）

### 2.1 安装 Node.js

从 [Node.js 官网](https://nodejs.org/) 下载并安装 LTS 版本。

验证安装：

```bash
node --version
npm --version
```

### 2.2 安装 pnpm（推荐）

```bash
npm install -g pnpm
```

### 2.3 安装前端依赖

```bash
cd front-end

pnpm install
```

或使用 npm：

```bash
npm install
```

### 2.4 主要依赖说明

| 依赖 | 版本 | 说明 |
|------|------|------|
| vue | ^3.5.26 | Vue3 框架 |
| element-plus | ^2.13.4 | UI 组件库 |
| echarts | ^5.6.0 | 图表库 |
| pinia | ^3.0.4 | 状态管理 |
| vite | ^7.3.0 | 构建工具 |
| @vueuse/core | ^14.2.1 | Vue 组合式工具库 |

---

## 三、项目运行

### 3.1 开发模式

**步骤 1：启动后端**

```bash
cd 毕业设计
python app.py
```

**步骤 2：启动前端开发服务器**

```bash
cd front-end
pnpm dev
```

访问 `http://localhost:5173` 即可使用。

### 3.2 生产模式

**步骤 1：打包前端**

```bash
cd front-end
pnpm build
```

打包产物生成在 `front-end/dist` 目录。

**步骤 2：启动后端服务**

```bash
python app.py
```

Flask 会自动托管 `dist` 目录下的静态文件，访问 `http://127.0.0.1:5000` 即可。

---

## 四、常见问题

### 4.1 端口占用

若 5000 端口被占用，可在 `app.py` 中修改端口：

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
```

### 4.2 跨域问题

后端已配置 `flask-cors`，默认允许跨域访问。如需限制，可修改 `app.py` 中的 CORS 配置。

### 4.3 Node 版本不兼容

使用 nvm 切换 Node 版本：

```bash
nvm install 20
nvm use 20
```

---

## 五、项目结构

```
毕业设计/
├── app.py                 # Flask 后端入口
├── requirements.txt       # Python 依赖
├── front-end/             # Vue3 前端项目
│   ├── src/
│   │   ├── views/         # 页面组件
│   │   ├── components/    # 通用组件
│   │   ├── stores/        # Pinia 状态管理
│   │   └── main.js        # 入口文件
│   ├── public/            # 静态资源
│   ├── package.json       # 前端依赖配置
│   └── vite.config.js     # Vite 配置
└── README.md
```

---

## 六、相关命令速查

| 命令 | 说明 |
|------|------|
| `python app.py` | 启动后端服务 |
| `pnpm dev` | 启动前端开发服务器 |
| `pnpm build` | 打包前端生产版本 |
| `pnpm preview` | 预览打包后的版本 |
| `pip install -r requirements.txt` | 安装后端依赖 |
