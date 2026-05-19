# PriceReader

[![CI](https://github.com/czgreat/pricereader/actions/workflows/ci.yml/badge.svg)](https://github.com/czgreat/pricereader/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Language:** English | [中文](README.zh-CN.md)

Self-hosted deal monitoring service with source adapters, deterministic rules, storage, scheduling, and notification hooks.

## Overview

PriceReader monitors configured public sources, normalizes items, evaluates deterministic rules, stores matches, and can notify downstream services.

## Key Features

- Source adapter architecture
- Runtime source and rule configuration APIs
- Keyword, spec, and price ceiling rules
- Scheduler, source health checks, and pause/resume controls
- Stored item, evaluation, match, muted item, and notification views

## Current Public Release

Ready to use:

- Run locally with SQLite and example config
- Run full test suite with pytest
- Use Docker on port 8000
- Replace example rules with your private config

You must provide locally:

- Your own `config.yml` based on `config.example.yml`
- Allowed source URLs and polling intervals
- Optional notification webhook URL
- Network/proxy settings if required by your environment

## Quick Start

```bash
cp .env.example .env
cp config.example.yml config.yml
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

For Python projects on Windows, activate the virtual environment with `.venv\Scripts\Activate.ps1` instead of `. .venv/bin/activate`.

## Docker Deployment

```bash
cp .env.example .env
cp config.example.yml config.yml
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
curl http://localhost:8000/healthz
```

## Manual Deployment

- Install Python 3.11.
- Create a virtual environment and run `pip install -e ".[dev]"`.
- Copy `config.example.yml` to a private config file.
- Set `PRICEREADER_CONFIG` to that file and run `uvicorn app.main:app --reload`.

## Configuration

- `PRICEREADER_CONFIG`: path to your private config file
- `DATABASE_URL`: SQLite or other supported database URL
- `NOTIFY_WEBHOOK_URL`: optional notification endpoint
- `HTTP_PROXY`, `HTTPS_PROXY`: optional proxy settings
- `LOG_LEVEL`: runtime log verbosity

## API Surface

- `GET /healthz` for health checks
- `GET /api/v1/summary` for dashboard summary
- `GET/PUT/POST/DELETE /api/v1/sources*` for source config
- `GET/PUT/POST/DELETE /api/v1/rules*` for rule config
- `POST /api/v1/sync/run-all` to run sync/evaluation

## Validation

```bash
pytest
python -m compileall app tests
```

## Repository Layout

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app entrypoint |
| `app/api/routes.py` | Runtime API routes |
| `app/` | Adapters, extraction, storage, rules, notifications, scheduler |
| `tests/` | Behavior and API tests |
| `config.example.yml` | Public-safe config template |

## Documentation

| Topic | English | Chinese |
|---|---|---|
| Deployment | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | [docs/DEPLOYMENT.zh-CN.md](docs/DEPLOYMENT.zh-CN.md) |
| AI handoff | [docs/AI_HANDOFF.md](docs/AI_HANDOFF.md) | [docs/AI_HANDOFF.zh-CN.md](docs/AI_HANDOFF.zh-CN.md) |
| Roadmap | [docs/ROADMAP.md](docs/ROADMAP.md) | [docs/ROADMAP.zh-CN.md](docs/ROADMAP.zh-CN.md) |

## AI-Assisted Development

This public release was prepared with Codex using GPT-5.4 and GPT-5.5 assistance. The source code, docs, and public-release cleanup were reviewed for public sharing, but this is a community project and not an official OpenAI product.

Good next tasks for an AI coding assistant:

- Add new source adapters
- Add UI tests for runtime config editing
- Improve duplicate/mute workflows
- Add auth and audit logging for shared deployments

## Privacy and Secrets

Do not commit real `.env` files, API keys, webhook secrets, cookies, private media, production databases, logs, generated artifacts, or personal data. Start from the example config files and keep private values outside Git.

## License

MIT
