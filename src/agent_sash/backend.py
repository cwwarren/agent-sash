from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import httpx

from agent_sash.config import Config


def ensure_runtime_dirs(config: Config) -> None:
    config.pid_file.parent.mkdir(parents=True, exist_ok=True)
    config.log_file.parent.mkdir(parents=True, exist_ok=True)


def read_pid(config: Config) -> int | None:
    if not config.pid_file.exists():
        return None
    text = config.pid_file.read_text().strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        config.pid_file.unlink(missing_ok=True)
        return None


def is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def remove_stale_pid(config: Config) -> None:
    pid = read_pid(config)
    if pid is None:
        return
    if is_process_alive(pid):
        return
    config.pid_file.unlink(missing_ok=True)


def log_tail(path: Path, lines: int = 40) -> str:
    if not path.exists():
        return ""
    content = path.read_text(errors="replace").splitlines()
    return "\n".join(content[-lines:])


def health_url(config: Config) -> str:
    return f"{config.base_url}/v1/models"


def list_model_ids(config: Config, *, timeout: float = 5.0) -> list[str]:
    with httpx.Client(timeout=timeout) as client:
        response = client.get(health_url(config))
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("server returned no models")
    ids = [item.get("id") for item in data if isinstance(item, dict)]
    valid_ids = [item for item in ids if isinstance(item, str) and item]
    if not valid_ids:
        raise RuntimeError("server returned invalid model ids")
    return valid_ids


def is_healthy(config: Config) -> bool:
    try:
        return bool(list_model_ids(config, timeout=2.0))
    except Exception:
        return False


def get_model_id(config: Config) -> str:
    return list_model_ids(config)[0]


def build_command(config: Config) -> list[str]:
    if config.backend == "mlx":
        return [
            sys.executable,
            "-m",
            "mlx_lm.server",
            "--model",
            str(config.model_path),
            "--host",
            config.host,
            "--port",
            str(config.port),
        ]
    if config.backend == "llama_cpp":
        return [
            "llama-server",
            "-m",
            str(config.model_path),
            "--host",
            config.host,
            "--port",
            str(config.port),
        ]
    raise RuntimeError(f"unknown backend: {config.backend}")


def wait_for_ready(config: Config, *, timeout: float, process: subprocess.Popen) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_healthy(config):
            return True
        if process.poll() is not None:
            return False
        time.sleep(0.5)
    return False


def start_server(config: Config) -> str:
    ensure_runtime_dirs(config)
    remove_stale_pid(config)
    if is_healthy(config):
        return "already running"
    if config.backend == "llama_cpp" and not Path(config.model_path).exists():
        raise RuntimeError(f"model path not found: {config.model_path}")
    command = build_command(config)
    cache_dir = config.log_file.parent / "hf-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("HF_HUB_CACHE", str(cache_dir))
    env.setdefault("HF_HOME", str(cache_dir.parent / "hf-home"))
    with config.log_file.open("ab") as log:
        process = subprocess.Popen(
            command,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    config.pid_file.write_text(f"{process.pid}\n")
    if wait_for_ready(config, timeout=config.startup_timeout_seconds, process=process):
        return "started"
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    config.pid_file.unlink(missing_ok=True)
    tail = log_tail(config.log_file)
    raise RuntimeError(f"server failed to start\n{tail}")


def stop_server(config: Config) -> str:
    pid = read_pid(config)
    if pid is None:
        config.pid_file.unlink(missing_ok=True)
        return "not running"
    if not is_process_alive(pid):
        config.pid_file.unlink(missing_ok=True)
        return "not running"
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        config.pid_file.unlink(missing_ok=True)
        return "stopped"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not is_process_alive(pid):
            config.pid_file.unlink(missing_ok=True)
            return "stopped"
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        config.pid_file.unlink(missing_ok=True)
        return "stopped"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not is_process_alive(pid):
            config.pid_file.unlink(missing_ok=True)
            return "stopped"
        time.sleep(0.2)
    raise RuntimeError(f"failed to stop pid {pid}")
