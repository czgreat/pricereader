# Deployment Guide

Self-hosted deal monitoring service with source adapters, rules, scheduler, storage, and optional notifications.

## What is already usable

- FastAPI app and tests are included
- Rule/config system is included
- Example config is included
- Webhook notifier is optional

## What you must provide

- Private rule file with your own keywords and price thresholds
- Decision on which source adapters are legal and appropriate for your use
- Notification webhook if desired
- Persistent data directory

## Local development

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

## Validation checks

```bash
pytest
python -m compileall app tests
```

## Docker deployment

```bash
cp .env.example .env
cp docker-compose.example.yml docker-compose.yml
docker compose up --build
```

## Manual deployment

Keep your real rules in a private YAML file outside the repository, point `PRICEREADER_CONFIG` to it, and run the FastAPI service with persistent storage mounted.

## Production checklist

- Keep `.env` private and never commit it.
- Replace all placeholder secrets before exposing the service.
- Mount runtime data outside the repository.
- Put the service behind HTTPS if it is reachable from other machines.
- Back up persistent data before upgrades.
- Review logs after the first startup.

