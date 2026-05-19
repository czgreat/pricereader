# AI Handoff Guide

**Language:** English | [中文](AI_HANDOFF.zh-CN.md)

Use this file when handing `pricereader` to an AI coding assistant. It gives the assistant enough context to make useful changes without depending on private deployment history.

## First 15 Minutes

1. Read `README.md`, this file, and `docs/DEPLOYMENT.md`.
2. Inspect the repository layout table in `README.md`.
3. Run the validation command before editing anything substantial.
4. Confirm whether the task is documentation, tests, local deployment, or product code.
5. Keep all private credentials, state, media, and production data outside the repository.

## Project Summary

PriceReader monitors configured public sources, normalizes items, evaluates deterministic rules, stores matches, and can notify downstream services.

## Important Paths

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app entrypoint |
| `app/api/routes.py` | Runtime API routes |
| `app/` | Adapters, extraction, storage, rules, notifications, scheduler |
| `tests/` | Behavior and API tests |
| `config.example.yml` | Public-safe config template |

## Good First Tasks

- Add new source adapters
- Add UI tests for runtime config editing
- Improve duplicate/mute workflows
- Add auth and audit logging for shared deployments

## Context To Provide To An AI Assistant

- The repository URL and branch.
- Your operating system and runtime versions.
- The exact command that fails or the exact workflow you want improved.
- Sanitized logs with secrets removed.
- Whether you are using local development, Docker, or manual deployment.
- Any constraints around privacy, public sharing, or supported platforms.

## Suggested Prompt

```text
You are working in the pricereader repository. Read README.md, docs/DEPLOYMENT.md, and docs/AI_HANDOFF.md first. Keep changes small, preserve public-safe examples, do not add real secrets, and run the documented validation command before summarizing changes.
```

## Guardrails

- Do not add private `.env` values, API keys, cookies, webhook secrets, local IP addresses, production URLs, personal records, or generated artifacts.
- Prefer focused tests over broad rewrites.
- Keep public examples generic and runnable on a clean machine.
- Update both English and Chinese docs when changing user-facing instructions.
- If deployment behavior changes, update `docs/DEPLOYMENT.md` and `docs/DEPLOYMENT.zh-CN.md` in the same change.

## Definition Of Done

- The requested behavior or documentation change is complete.
- Validation commands pass, or any skipped check is explicitly explained.
- README links still work.
- No private data or generated artifacts are committed.
