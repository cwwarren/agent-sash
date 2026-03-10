from __future__ import annotations

from agent_sash.config import load_config
from agent_sash.hook import decision_payload, extract_bash_command


def test_extract_bash_command() -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git push --force origin main"},
    }
    assert extract_bash_command(payload) == "git push --force origin main"


def test_extract_non_bash_command_returns_none() -> None:
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": "x"},
    }
    assert extract_bash_command(payload) is None


def test_decision_payload_shape() -> None:
    payload = decision_payload("ask", "agent-sash score 0.80: high impact")
    assert payload["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert payload["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert payload["suppressOutput"] is True


def test_config_threshold_contract() -> None:
    config = load_config()
    assert config.allow_below == 0.5
