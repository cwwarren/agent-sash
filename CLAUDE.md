# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

agent-sash is a Claude Code hook client that intercepts `PreToolUse` events, scores Bash commands via a locally-served LLM, and returns `allow`/`ask` decisions based on a risk threshold.

## Commands

```bash
uv sync                        # install dependencies
uv run pytest                  # run unit tests
uv run pytest -m e2e           # run e2e tests (needs local model)
uv run pytest -m "not e2e"     # skip e2e tests
uv run pytest tests/test_hook_unit.py::test_name  # run single test
```

## Architecture

Four modules in `src/agent_sash/`, no abstractions:

- **cli.py** — Three subcommands: `start`, `stop`, `claude-hook`. The hook subcommand reads JSON from stdin, scores it, writes decision JSON to stdout.
- **hook.py** — Core logic. Extracts bash commands from hook payloads, POSTs to `/v1/chat/completions` for a risk score (0-1), returns `allow` if below threshold, else `ask`. Falls back to `ask` on any error.
- **backend.py** — Manages the model server process (mlx on macOS, llama_cpp on Linux). PID file + health polling lifecycle.
- **config.py** — Frozen dataclass with built-in defaults. Every field overridable via `AGENT_SASH_*` env vars. Relative paths resolve from project dir.

## Conventions

- Python 3.13, managed by `uv`
- `from __future__ import annotations` in every file
- Python 3.10+ type syntax (`int | None`, `dict[str, str]`)
- Frozen dataclasses for data (`Config`, `Score`)
- Runtime files default to `~/.config/agent-sash/` (pid/logs/HF cache)
- E2e tests use `AGENT_SASH_TEST_MLX_MODEL` / `AGENT_SASH_TEST_LLAMA_MODEL` env vars to locate models
