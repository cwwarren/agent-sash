from __future__ import annotations

from dataclasses import dataclass
import json
import sys

import httpx

from agent_sash.backend import get_model_id, is_healthy, start_server
from agent_sash.config import Config

SYSTEM_PROMPT = (
    "You are a command risk scorer. Given a shell command, reply in exactly two parts. "
    "Line 1: a risk score from 0.0 to 1.0 with one decimal place. "
    "Line 2+: a brief explanation of the command's impact."
)


@dataclass(frozen=True)
class Score:
    score: float
    explanation: str


def load_hook_payload() -> dict:
    return json.load(sys.stdin)


def extract_bash_command(payload: dict) -> str | None:
    if payload.get("hook_event_name") != "PreToolUse":
        return None
    if payload.get("tool_name") != "Bash":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    return command


def ensure_server(config: Config) -> None:
    if is_healthy(config):
        return
    start_server(config)


def score_command(config: Config, command: str) -> Score:
    ensure_server(config)
    model = get_model_id(config)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": command},
        ],
        "max_tokens": 150,
        "temperature": 0.0,
    }
    with httpx.Client(timeout=config.score_timeout_seconds) as client:
        response = client.post(f"{config.base_url}/v1/chat/completions", json=payload)
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("server returned no choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise RuntimeError("server returned no message")
    content = message.get("content")
    if not isinstance(content, str):
        raise RuntimeError("server returned non-string content")
    lines = content.strip().split("\n", 1)
    raw_score = lines[0].strip()
    try:
        score = float(raw_score)
    except ValueError:
        raise RuntimeError(f"model returned non-numeric score: {raw_score!r}")
    explanation = lines[1].strip() if len(lines) > 1 else ""
    if not explanation:
        raise RuntimeError("model returned no explanation")
    return Score(score=max(0.0, min(1.0, score)), explanation=explanation)


def decision_payload(decision: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        },
        "suppressOutput": True,
    }


def evaluate_command(config: Config, command: str) -> dict:
    try:
        result = score_command(config, command)
    except Exception as exc:
        return decision_payload("ask", f"agent-sash could not score command: {exc}")
    reason = f"agent-sash score {result.score:.2f}: {result.explanation}"
    if result.score < config.allow_below:
        return decision_payload("allow", reason)
    return decision_payload("ask", reason)
