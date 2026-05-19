# PriceReader / 价格监控服务

[![CI](https://github.com/czgreat/pricereader/actions/workflows/ci.yml/badge.svg)](https://github.com/czgreat/pricereader/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**语言：** [English](README.md) | 中文

自托管价格/优惠监控服务，包含来源适配器、确定性规则、存储、调度和通知钩子。

## 概览

PriceReader 会监控配置的公开来源，标准化条目，执行确定性规则，保存命中结果，并可通知下游服务。

## 主要功能

- 来源适配器架构
- 运行时来源和规则配置 API
- 关键词、规格和价格上限规则
- 调度器、来源健康检查和暂停/恢复控制
- 存储条目、评估、命中、静音条目和通知视图

## 当前公开版状态

已经可以使用：

- 可用 SQLite 和示例配置本地运行
- 可用 pytest 跑完整测试
- 可用 Docker 在 8000 端口运行
- 可用你的私有配置替换示例规则

需要你在本地补全：

- 基于 `config.example.yml` 准备自己的 `config.yml`
- 允许监控的来源 URL 和轮询间隔
- 可选通知 webhook URL
- 如环境需要，配置网络/代理

## 快速开始

```bash
cp .env.example .env
cp config.example.yml config.yml
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

如果在 Windows PowerShell 使用 Python 虚拟环境，请用 `.venv\Scripts\Activate.ps1`，不要用 `. .venv/bin/activate`。

## Docker 部署

```bash
cp .env.example .env
cp config.example.yml config.yml
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
curl http://localhost:8000/healthz
```

## 手工部署

- 安装 Python 3.11。
- 创建虚拟环境并执行 `pip install -e ".[dev]"`。
- 把 `config.example.yml` 复制为私有配置文件。
- 设置 `PRICEREADER_CONFIG` 指向该文件，再执行 `uvicorn app.main:app --reload`。

## 配置说明

- `PRICEREADER_CONFIG`：私有配置文件路径
- `DATABASE_URL`：SQLite 或其他支持的数据库 URL
- `NOTIFY_WEBHOOK_URL`：可选通知端点
- `HTTP_PROXY`、`HTTPS_PROXY`：可选代理配置
- `LOG_LEVEL`：运行日志级别

## API 概览

- `GET /healthz` 健康检查
- `GET /api/v1/summary` 仪表盘摘要
- `GET/PUT/POST/DELETE /api/v1/sources*` 来源配置
- `GET/PUT/POST/DELETE /api/v1/rules*` 规则配置
- `POST /api/v1/sync/run-all` 执行同步和评估

## 验证命令

```bash
pytest
python -m compileall app tests
```

## 仓库结构

| 路径 | 说明 |
|---|---|
| `app/main.py` | FastAPI 应用入口 |
| `app/api/routes.py` | 运行时 API 路由 |
| `app/` | 适配器、抽取、存储、规则、通知和调度 |
| `tests/` | 行为和 API 测试 |
| `config.example.yml` | 可公开的配置模板 |

## 更多文档

| 主题 | 中文 | English |
|---|---|---|
| 部署 | [docs/DEPLOYMENT.zh-CN.md](docs/DEPLOYMENT.zh-CN.md) | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| AI 接手 | [docs/AI_HANDOFF.zh-CN.md](docs/AI_HANDOFF.zh-CN.md) | [docs/AI_HANDOFF.md](docs/AI_HANDOFF.md) |
| 路线图 | [docs/ROADMAP.zh-CN.md](docs/ROADMAP.zh-CN.md) | [docs/ROADMAP.md](docs/ROADMAP.md) |

## AI 辅助开发说明

这个公开版由 Codex 使用 GPT-5.4 和 GPT-5.5 辅助整理完成。源码、文档和公开前清理都经过面向公开分享的复核，但本项目是社区项目，不是 OpenAI 官方产品。

适合继续交给 AI coding assistant 的任务：

- 增加新的来源适配器
- 增加运行时配置编辑的 UI 测试
- 改进重复项/静音流程
- 为共享部署增加鉴权和审计日志

## 隐私和密钥

不要提交真实 `.env`、API key、webhook secret、cookies、私人媒体、生产数据库、日志、生成产物或个人数据。请从示例配置开始，把私有值保存在 Git 之外。

## License

MIT
