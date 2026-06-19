"""Configuration loading for desktop runtime and packaging flows."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any


@dataclass
class AppConfig:
    theme: str
    hotkey: str
    overlay_opacity: float
    data_directory: str
    log_directory: str


@dataclass
class ModelConfig:
    stt_model: str
    llm_model: str
    offline_fallback_enabled: bool
    llm_base_url: str = "http://127.0.0.1:11434/api/generate"
    llm_timeout_seconds: float = 15.0
    llm_api_key_env: str = "MISTRAL_API_KEY"
    llm_fallback_model: str = "mistral-small-latest"
    llm_fallback_base_url: str = "https://api.mistral.ai/v1/chat/completions"


@dataclass
class PremiumConfig:
    premium: bool
    features: list[str]
    packaging_targets: list[str]
    mobile_follow_up: dict[str, Any]


@dataclass
class RuntimeConfig:
    app: AppConfig
    model: ModelConfig
    premium: PremiumConfig


def default_config_dir() -> Path:
    bundled = Path(__file__).resolve().parent / "config"
    if bundled.is_dir():
        return bundled
    if getattr(sys, "frozen", False):
        fallback = Path(sys.executable).resolve().parent / "desktop_app" / "config"
        if fallback.is_dir():
            return fallback
        internal = Path(sys.executable).resolve().parent / "_internal" / "desktop_app" / "config"
        if internal.is_dir():
            return internal
    return bundled


def load_runtime_config(config_dir: str | Path | None = None) -> RuntimeConfig:
    resolved_dir = Path(config_dir) if config_dir else default_config_dir()
    app_payload = _load_json_file(resolved_dir / "app_config.json")
    model_payload = _load_json_file(resolved_dir / "model_config.json")
    premium_payload = _load_json_file(resolved_dir / "premium_config.json")

    return RuntimeConfig(
        app=AppConfig(**app_payload),
        model=ModelConfig(**model_payload),
        premium=PremiumConfig(**premium_payload),
    )


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text)