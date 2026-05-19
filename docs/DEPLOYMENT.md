# Deployment Guide

**Language:** English | [中文](DEPLOYMENT.zh-CN.md)

This guide explains how to run `pricereader` locally, in Docker, or with a manual service setup. It assumes you cloned the GitHub repository and are working from the repository root.

## What Is Already Usable

- Run locally with SQLite and example config
- Run full test suite with pytest
- Use Docker on port 8000
- Replace example rules with your private config

## What You Must Provide

- Your own `config.yml` based on `config.example.yml`
- Allowed source URLs and polling intervals
- Optional notification webhook URL
- Network/proxy settings if required by your environment

## Local Development

```bash
cp .env.example .env
cp config.example.yml config.yml
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

If the command uses `. .venv/bin/activate`, use `.venv\Scripts\Activate.ps1` on Windows PowerShell.

## Docker Deployment

```bash
cp .env.example .env
cp config.example.yml config.yml
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
curl http://localhost:8000/healthz
```

Before running Docker, review every bind mount and every value in `.env`. Example compose files are intentionally generic and should be adjusted to your host paths and ports.

## Manual Deployment

- Install Python 3.11.
- Create a virtual environment and run `pip install -e ".[dev]"`.
- Copy `config.example.yml` to a private config file.
- Set `PRICEREADER_CONFIG` to that file and run `uvicorn app.main:app --reload`.

## Configuration Checklist

- `PRICEREADER_CONFIG`: path to your private config file
- `DATABASE_URL`: SQLite or other supported database URL
- `NOTIFY_WEBHOOK_URL`: optional notification endpoint
- `HTTP_PROXY`, `HTTPS_PROXY`: optional proxy settings
- `LOG_LEVEL`: runtime log verbosity

## Validation Checks

```bash
pytest
python -m compileall app tests
```

## Production Checklist

- Replace all placeholder secrets before real use.
- Keep private config, generated data, logs, uploaded media, and generated artifacts outside Git.
- Put the service behind a reverse proxy with HTTPS if it is reachable from other devices.
- Add authentication before exposing private APIs beyond localhost.
- Configure backups for any database, state directory, uploaded files, and generated artifacts.
- Read `SECURITY.md` before reporting or triaging security issues.

## Troubleshooting

- Re-check `.env` and volume paths first; most deployment failures are path or permission issues.
- Use the health endpoint listed in `README.md` to separate process startup issues from application behavior.
- Run the validation commands before changing deployment infrastructure.
- When asking an AI assistant for help, include OS, runtime versions, exact command, sanitized logs, and deployment mode.
