# Roadmap

**Language:** English | [中文](ROADMAP.zh-CN.md)

This roadmap describes the public repository state for `pricereader`. It separates what is ready to use from what each user should complete in their own environment.

## Complete Enough To Use

- Rule engine and adapters
- Runtime config APIs
- Scheduler and notification pipeline
- Pytest suite

## Needs Local Completion

- Private source/rule configuration
- Production notification target
- Rate-limit and politeness settings for your source list
- Authentication if exposed beyond localhost

## Suggested Improvements

- Add new source adapters
- Add UI tests for runtime config editing
- Improve duplicate/mute workflows
- Add auth and audit logging for shared deployments

## Documentation Still Worth Adding

- Screenshots or short screen recordings using non-private demo data.
- A fuller API example page for common requests and responses.
- Backup and restore notes for any persistent data path.
- A troubleshooting page based on real public issues once users start deploying it.

## Maintenance Notes

- Keep public examples generic.
- Keep English and Chinese instructions aligned.
- Prefer small issues and pull requests so AI-assisted contributors can work safely.
- Re-run sensitive-data scans before publishing new releases.
