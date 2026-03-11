from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

import httpx
import pytest


from agent_sash.config import DEFAULT_MODEL_PATH

PROJECT_DIR = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def cli_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["AGENT_SASH_HOST"] = "127.0.0.1"
    env["AGENT_SASH_PORT"] = str(free_port())
    env["AGENT_SASH_PID_FILE"] = str(tmp_path / "agent-sash.pid")
    env["AGENT_SASH_LOG_FILE"] = str(tmp_path / "agent-sash.log")
    if sys.platform == "darwin":
        env["AGENT_SASH_BACKEND"] = "mlx"
        env["AGENT_SASH_MODEL_PATH"] = os.getenv("AGENT_SASH_TEST_MLX_MODEL", DEFAULT_MODEL_PATH)
    elif sys.platform.startswith("linux"):
        model_path = os.getenv("AGENT_SASH_TEST_LLAMA_MODEL")
        if not model_path or not shutil.which("llama-server"):
            pytest.skip("llama.cpp backend not configured")
        env["AGENT_SASH_BACKEND"] = "llama_cpp"
        env["AGENT_SASH_MODEL_PATH"] = model_path
    else:
        pytest.skip(f"unsupported platform: {sys.platform}")
    return env


def run_cli(*args: str, env: dict[str, str], stdin: str | None = None, timeout: float = 180.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "agent_sash", *args],
        cwd=PROJECT_DIR,
        env=env,
        input=stdin,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def wait_for_server(port: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/v1/models"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise AssertionError("server did not become healthy")


@pytest.mark.e2e
def test_start_stop_idempotent_real_backend(tmp_path: Path) -> None:
    env = cli_env(tmp_path)
    start = run_cli("start", env=env)
    assert start.returncode == 0, start.stderr
    wait_for_server(int(env["AGENT_SASH_PORT"]))

    start_again = run_cli("start", env=env)
    assert start_again.returncode == 0, start_again.stderr

    stop = run_cli("stop", env=env)
    assert stop.returncode == 0, stop.stderr

    stop_again = run_cli("stop", env=env)
    assert stop_again.returncode == 0, stop_again.stderr


@pytest.mark.e2e
def test_claude_hook_autostarts_and_scores(tmp_path: Path) -> None:
    env = cli_env(tmp_path)
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git push --force origin main"},
    }
    result = run_cli("claude-hook", env=env, stdin=json.dumps(payload), timeout=240.0)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert output["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "agent-sash score" in output["hookSpecificOutput"]["permissionDecisionReason"]

    stop = run_cli("stop", env=env)
    assert stop.returncode == 0, stop.stderr


def test_claude_hook_ignores_non_bash(tmp_path: Path) -> None:
    env = cli_env(tmp_path)
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": "x"},
    }
    result = run_cli("claude-hook", env=env, stdin=json.dumps(payload))
    assert result.returncode == 0
    assert result.stdout == ""
