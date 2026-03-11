from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8081
DEFAULT_MODEL_PATH = "cwrn/Qwen3.5-0.8B-SHGuard-MLX-Q8"
DEFAULT_RUNTIME_DIR = Path.home() / ".config" / "agent-sash"
DEFAULT_PID_FILE = DEFAULT_RUNTIME_DIR / "agent-sash.pid"
DEFAULT_LOG_FILE = DEFAULT_RUNTIME_DIR / "agent-sash.log"
DEFAULT_STARTUP_TIMEOUT_SECONDS = 120.0
DEFAULT_SCORE_TIMEOUT_SECONDS = 30.0
DEFAULT_ALLOW_BELOW = 0.5


@dataclass(frozen=True)
class Config:
    backend: str
    host: str
    port: int
    model_path: str
    pid_file: Path
    log_file: Path
    startup_timeout_seconds: float
    score_timeout_seconds: float
    allow_below: float

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


def default_backend() -> str:
    if sys.platform == "darwin":
        return "mlx"
    if sys.platform.startswith("linux"):
        return "llama_cpp"
    raise RuntimeError(f"unsupported platform: {sys.platform}")


def resolve_path(raw: str, *, base: Path) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (base / path).resolve()


def resolve_model_path(raw: str, *, base: Path) -> str:
    candidate = resolve_path(raw, base=base)
    if candidate.exists():
        return str(candidate)
    return raw


def getenv(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def load_config() -> Config:
    backend = getenv("AGENT_SASH_BACKEND", default_backend())
    host = getenv("AGENT_SASH_HOST", DEFAULT_HOST)
    port = int(getenv("AGENT_SASH_PORT", str(DEFAULT_PORT)))
    model_path = resolve_model_path(getenv("AGENT_SASH_MODEL_PATH", DEFAULT_MODEL_PATH), base=PROJECT_DIR)
    pid_file = resolve_path(getenv("AGENT_SASH_PID_FILE", str(DEFAULT_PID_FILE)), base=PROJECT_DIR)
    log_file = resolve_path(getenv("AGENT_SASH_LOG_FILE", str(DEFAULT_LOG_FILE)), base=PROJECT_DIR)
    startup_timeout_seconds = float(getenv("AGENT_SASH_STARTUP_TIMEOUT", str(DEFAULT_STARTUP_TIMEOUT_SECONDS)))
    score_timeout_seconds = float(getenv("AGENT_SASH_SCORE_TIMEOUT", str(DEFAULT_SCORE_TIMEOUT_SECONDS)))
    allow_below = float(getenv("AGENT_SASH_ALLOW_BELOW", str(DEFAULT_ALLOW_BELOW)))
    return Config(
        backend=backend,
        host=host,
        port=port,
        model_path=model_path,
        pid_file=pid_file,
        log_file=log_file,
        startup_timeout_seconds=startup_timeout_seconds,
        score_timeout_seconds=score_timeout_seconds,
        allow_below=allow_below,
    )
