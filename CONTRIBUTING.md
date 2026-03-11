# Contributing to Voice Agent

Thanks for your interest in contributing.

## Development setup

1. Fork and clone this repository.
2. Install dependencies with `uv`.
3. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`.

```bash
cp .env.example .env
uv run pytest tests/
```

## Development workflow

- Use Python 3.11+.
- Run all commands with `uv run`.
- Keep changes focused and small.
- Add or update tests when behavior changes.
- Preserve existing architecture and audio format contracts.

## Code style

- Use type hints throughout.
- Prefer explicit, readable async flow.
- Keep cancellation cooperative and non-blocking.
- Follow existing module patterns (`__future__` imports, module logger).

## Pull requests

- Open a PR with a clear title and rationale.
- Describe user-visible behavior changes.
- Include test evidence (`uv run pytest tests/`).
- Link related issues when applicable.

## Reporting bugs

Please include:

- OS and Python version
- Reproduction steps
- Expected vs actual behavior
- Relevant logs

## Security issues

Do not open public issues for vulnerabilities. Follow `SECURITY.md`.
