# 部署说明

**语言：** [English](DEPLOYMENT.md) | 中文

本文说明如何在本地、Docker 或手工服务模式下运行 `pricereader`。默认你已经 clone 了 GitHub 仓库，并在仓库根目录操作。

## 已经可以使用

- 可用 SQLite 和示例配置本地运行
- 可用 pytest 跑完整测试
- 可用 Docker 在 8000 端口运行
- 可用你的私有配置替换示例规则

## 你需要自己提供

- 基于 `config.example.yml` 准备自己的 `config.yml`
- 允许监控的来源 URL 和轮询间隔
- 可选通知 webhook URL
- 如环境需要，配置网络/代理

## 本地开发

```bash
cp .env.example .env
cp config.example.yml config.yml
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

如果命令里出现 `. .venv/bin/activate`，Windows PowerShell 下请改用 `.venv\Scripts\Activate.ps1`。

## Docker 部署

```bash
cp .env.example .env
cp config.example.yml config.yml
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
curl http://localhost:8000/healthz
```

运行 Docker 前，请先检查所有 volume 映射和 `.env`。示例 compose 文件只提供通用起点，需要按你的主机路径和端口修改。

## 手工部署

- 安装 Python 3.11。
- 创建虚拟环境并执行 `pip install -e ".[dev]"`。
- 把 `config.example.yml` 复制为私有配置文件。
- 设置 `PRICEREADER_CONFIG` 指向该文件，再执行 `uvicorn app.main:app --reload`。

## 配置检查清单

- `PRICEREADER_CONFIG`：私有配置文件路径
- `DATABASE_URL`：SQLite 或其他支持的数据库 URL
- `NOTIFY_WEBHOOK_URL`：可选通知端点
- `HTTP_PROXY`、`HTTPS_PROXY`：可选代理配置
- `LOG_LEVEL`：运行日志级别

## 验证命令

```bash
pytest
python -m compileall app tests
```

## 生产检查清单

- 真实使用前替换所有占位密钥。
- 私有配置、生成数据、日志、上传文件和产物不要放进 Git。
- 如果服务会被其他设备访问，请放到启用 HTTPS 的反向代理后面。
- 私有 API 暴露到 localhost 以外前，请先增加鉴权。
- 为数据库、状态目录、上传文件和生成产物配置备份。
- 处理安全问题前先阅读 `SECURITY.md`。

## 排障建议

- 先复查 `.env` 和 volume 路径；多数部署问题来自路径或权限。
- 用 `README.md` 里列出的健康检查接口区分进程启动问题和业务问题。
- 修改部署基础设施前，先跑验证命令。
- 让 AI assistant 帮忙时，提供操作系统、运行时版本、完整命令、去敏日志和部署模式。
