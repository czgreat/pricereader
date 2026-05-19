# PriceReader

PriceReader is a self-hosted deal monitoring service. It combines source adapters, deterministic rules, price/spec extraction, and notification hooks.

## Features

- Source adapter architecture
- Keyword, spec, and price-ceiling rules
- Runtime configuration API
- Scheduler and source health checks
- Optional webhook notifications

## Public Repository Scope

This repository includes framework code and example configuration only. Real monitoring keywords, private allowlists, notification URLs, and caches are intentionally excluded.

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
