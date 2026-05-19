# PriceReader / 价格监控服务

[English](README.md) | [中文](README.zh-CN.md)

PriceReader 是一个自托管价格/好价监控服务，包含数据源适配器、确定性规则、信息抽取、存储、调度、运行时控制和可选 webhook 通知。


## AI 辅助开发说明

这个公开版由 Codex 在 GPT-5.4 / GPT-5.5 辅助下整理完成。代码、文档和公开前清理已按公开仓库标准处理，但本项目不是 OpenAI 官方产品。


## 功能

- 数据源适配器架构
- 关键词、规格、价格上限规则
- 运行时配置 API
- 调度器和数据源健康检查
- 命中结果视图和通知流水线
- 可选 webhook 通知
- FastAPI 服务，并带 pytest 覆盖

## 公开版范围

这个公开仓库只包含框架代码和示例配置，不包含真实监控关键词、私有白名单、通知地址、cookies、缓存或生产数据。

## 快速开始

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

本地运行：

```bash
uvicorn app.main:app --reload
```

Docker：

```bash
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
```

## 配置

从 `config.example.yml` 开始，把 `PRICEREADER_CONFIG` 指向你自己的私有配置文件。真实规则不要提交到公开仓库。

## License

MIT

