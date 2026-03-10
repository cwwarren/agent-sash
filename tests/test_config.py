from __future__ import annotations

from pathlib import Path

from agent_sash.config import PROJECT_DIR, default_backend, load_config


def test_load_config_defaults() -> None:
    config = load_config()
    assert config.host == "127.0.0.1"
    assert config.port == 8081
    assert config.allow_below == 0.5
    assert config.pid_file.is_absolute()
    assert config.log_file.is_absolute()


def test_default_backend_matches_platform() -> None:
    backend = default_backend()
    assert backend in {"mlx", "llama_cpp"}


def test_default_model_path_is_repo_relative() -> None:
    config = load_config()
    assert isinstance(config.model_path, str)
    assert config.model_path
