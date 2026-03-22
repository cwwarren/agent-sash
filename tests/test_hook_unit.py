from __future__ import annotations

import pytest

from agent_sash.cli import build_parser, parse_allow
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


def test_parse_allow_valid() -> None:
    assert parse_allow("<0.4") == 0.4
    assert parse_allow("<0.0") == 0.0
    assert parse_allow("<1.0") == 1.0


def test_parse_allow_rejects_missing_lt() -> None:
    with pytest.raises(ValueError, match="must start with '<'"):
        parse_allow("0.4")


def test_parse_allow_rejects_non_float() -> None:
    with pytest.raises(ValueError):
        parse_allow("<abc")


def test_claude_hook_parser_allow_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["claude-hook", "--allow", "<0.3"])
    assert args.allow == "<0.3"
    assert args.command == "claude-hook"


def test_claude_hook_parser_allow_default() -> None:
    parser = build_parser()
    args = parser.parse_args(["claude-hook"])
    assert args.allow is None
