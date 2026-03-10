from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tomllib


PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_DIR / "agent_sash.toml"


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
    path = Path(raw)
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
    with CONFIG_PATH.open("rb") as fh:
        raw = tomllib.load(fh)

    backend = getenv("AGENT_SASH_BACKEND", raw.get("backend") or default_backend())
    host = getenv("AGENT_SASH_HOST", raw["host"])
    port = int(getenv("AGENT_SASH_PORT", str(raw["port"])))
    model_path = resolve_model_path(getenv("AGENT_SASH_MODEL_PATH", raw["model_path"]), base=PROJECT_DIR)
    pid_file = resolve_path(getenv("AGENT_SASH_PID_FILE", raw["pid_file"]), base=PROJECT_DIR)
    log_file = resolve_path(getenv("AGENT_SASH_LOG_FILE", raw["log_file"]), base=PROJECT_DIR)
    startup_timeout_seconds = float(getenv("AGENT_SASH_STARTUP_TIMEOUT", str(raw["startup_timeout_seconds"])))
    score_timeout_seconds = float(getenv("AGENT_SASH_SCORE_TIMEOUT", str(raw["score_timeout_seconds"])))
    allow_below = float(getenv("AGENT_SASH_ALLOW_BELOW", str(raw["allow_below"])))
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
