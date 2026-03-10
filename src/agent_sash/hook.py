from __future__ import annotations

from dataclasses import dataclass
import json
import sys

import httpx

from agent_sash.backend import get_model_id, is_healthy, start_server
from agent_sash.config import Config

SYSTEM_PROMPT = (
    'You are a command risk scorer. Given a shell command, output a JSON object'
    ' with a "score" field (0.0 = no risk, 1.0 = catastrophic) and an'
    ' "explanation" field briefly describing the command\'s impact.'
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
        "max_tokens": 220,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
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
    parsed = json.loads(content)
    score = parsed.get("score")
    explanation = parsed.get("explanation")
    if not isinstance(score, int | float):
        raise RuntimeError("model returned invalid score")
    if not isinstance(explanation, str) or not explanation.strip():
        raise RuntimeError("model returned invalid explanation")
    return Score(score=float(score), explanation=explanation.strip())


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
