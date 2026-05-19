# PriceReader

[English](README.md) | [中文](README.zh-CN.md)

PriceReader is a self-hosted deal monitoring service. It combines source adapters, deterministic rules, extraction logic, storage, scheduling, runtime controls, and optional webhook notifications.


## AI-assisted development

This public release was prepared with Codex using GPT-5.4 and GPT-5.5 assistance. The code, documentation, and release cleanup were reviewed for public sharing, but the project is community-maintained and is not an official OpenAI product.


## Features

- Source adapter architecture
- Keyword, spec, and price-ceiling rules
- Runtime configuration API
- Scheduler and source health checks
- Rule match views and notification pipeline
- Optional webhook notifications
- FastAPI service with pytest coverage

## Public Repository Scope

This repository includes framework code and example configuration only. Real monitoring keywords, private allowlists, notification URLs, cookies, cache files, and production data are intentionally excluded.

## Quick Start

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Run locally:

```bash
uvicorn app.main:app --reload
```

Docker:

```bash
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
```

## Configuration

Start from `config.example.yml`, then point `PRICEREADER_CONFIG` to your own private config file. Keep real rules out of public commits.

## License

MIT

