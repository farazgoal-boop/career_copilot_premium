"""Flask app entrypoint for the live Career Copilot web dashboard."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, request

from runtime_paths import (
    briefing_storage_path,
    cache_root,
    configure_runtime_environment,
    default_bridge_base_url,
    profiles_root,
    repo_root,
    resolve_data_root,
    session_registry_path,
)

_REPO_ROOT = repo_root()


def _load_dotenv() -> None:
    """Load key=value pairs from .env without requiring python-dotenv."""
    from runtime_paths import load_env_file

    load_env_file()


def _resolve_secret_key() -> str:
    secret_key = os.environ.get("SECRET_KEY", "").strip()
    if secret_key:
        return secret_key
    return secrets.token_hex(32)


def _resolve_server_name_config() -> tuple[str, str] | None:
    raw_value = os.environ.get("SERVER_NAME", "").strip()
    if not raw_value:
        return None

    parsed = urlsplit(raw_value if "://" in raw_value else f"https://{raw_value}")
    server_name = parsed.netloc.strip() or parsed.path.strip().strip("/")
    if not server_name:
        return None

    preferred_scheme = parsed.scheme.strip() or "https"
    return server_name, preferred_scheme


def create_app() -> Flask:
    _load_dotenv()
    configure_runtime_environment()
    data_root = resolve_data_root()
    cache = cache_root(data_root)
    base = Path(__file__).resolve().parent

    try:
        cache.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    app = Flask(
        __name__,
        template_folder=str(base / "templates"),
        static_folder=str(base / "static"),
        static_url_path="/static",
    )

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.after_request
    def add_header(response):
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.config["SECRET_KEY"] = _resolve_secret_key()

    server_name_config = _resolve_server_name_config()
    if server_name_config:
        server_name, preferred_scheme = server_name_config
        app.config["SERVER_NAME"] = server_name
        app.config["PREFERRED_URL_SCHEME"] = preferred_scheme

    app.config["SESSION_REGISTRY_PATH"] = str(session_registry_path(data_root))
    app.config["BRIEFING_STORAGE_PATH"] = str(briefing_storage_path(data_root))
    app.config.setdefault("BRIEFING_PROFILES_ROOT", str(profiles_root(data_root)))

    bridge_url = os.environ.get("BRIDGE_BASE_URL", "").strip() or default_bridge_base_url()
    app.config["BRIDGE_BASE_URL"] = bridge_url

    from .routes import register_routes

    register_routes(app)
    return app


_app_instance: Flask | None = None


def get_app() -> Flask:
    global _app_instance
    if _app_instance is None:
        _app_instance = create_app()
    return _app_instance


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False, threaded=True)
