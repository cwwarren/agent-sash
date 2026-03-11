from __future__ import annotations

from agent_sash.config import (
    DEFAULT_ALLOW_BELOW,
    DEFAULT_HOST,
    DEFAULT_LOG_FILE,
    DEFAULT_PID_FILE,
    DEFAULT_PORT,
    default_backend,
    load_config,
)


def test_load_config_defaults() -> None:
    config = load_config()
    assert config.host == DEFAULT_HOST
    assert config.port == DEFAULT_PORT
    assert config.allow_below == DEFAULT_ALLOW_BELOW
    assert config.pid_file == DEFAULT_PID_FILE
    assert config.log_file == DEFAULT_LOG_FILE


def test_default_backend_matches_platform() -> None:
    backend = default_backend()
    assert backend in {"mlx", "llama_cpp"}


def test_default_model_path_is_non_empty() -> None:
    config = load_config()
    assert isinstance(config.model_path, str)
    assert config.model_path
