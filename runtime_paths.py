"""Shared filesystem and bridge URL resolution for dev, USB portable, and frozen installs."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import sys


APP_DIR_NAME = "CareerCopilotPremium"
MOBILE_BRIDGE_PORT = 8765
DASHBOARD_PORT = 5000
PORTABLE_FLAG_FILENAME = "portable.flag"


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def is_portable_mode() -> bool:
    """True when all data must stay inside the project/USB folder (no AppData)."""
    if install_root_is_readonly():
        return False
    portable_env = os.environ.get("CAREER_COPILOT_PORTABLE", "").strip().lower()
    if portable_env in {"1", "true", "yes", "on"}:
        return True
    return (repo_root() / PORTABLE_FLAG_FILENAME).is_file()


def _user_config_root() -> Path:
    """Per-user writable config/data root for installed desktop builds."""
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return (Path(local_app_data) / APP_DIR_NAME).resolve()
        return (Path.home() / "AppData" / "Local" / APP_DIR_NAME).resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / APP_DIR_NAME).resolve()
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg_config:
        return (Path(xdg_config) / APP_DIR_NAME).resolve()
    return (Path.home() / ".config" / APP_DIR_NAME).resolve()


def _appdata_data_root() -> Path:
    return _user_config_root()


def resolve_data_root() -> Path:
    configured = os.environ.get("DATA_ROOT", "").strip()
    if configured:
        return Path(configured).resolve()

    # Installed EXE under Program Files must never write next to the binary.
    if getattr(sys, "frozen", False) and install_root_is_readonly():
        return _appdata_data_root()

    if is_portable_mode():
        return repo_root()

    if getattr(sys, "frozen", False):
        return _appdata_data_root()

    if sys.platform == "darwin" or sys.platform.startswith("linux"):
        return _user_config_root()

    return repo_root()


def get_dashboard_port() -> int:
    raw = os.environ.get("DASHBOARD_PORT", "").strip()
    if raw.isdigit():
        return int(raw)
    return DASHBOARD_PORT


def install_root_is_readonly() -> bool:
    """True when the app folder cannot accept writes (e.g. Program Files install)."""
    root = repo_root()
    if getattr(sys, "frozen", False):
        lowered = str(root).casefold()
        if "program files" in lowered:
            return True
    try:
        return not os.access(root, os.W_OK)
    except OSError:
        return True


def primary_env_file_path() -> Path:
    """Writable .env path for API keys — never Program Files."""
    data_root = resolve_data_root()
    root = repo_root()
    if install_root_is_readonly() or not is_portable_mode():
        return data_root / ".env"
    if os.access(root, os.W_OK):
        return root / ".env"
    return data_root / ".env"


def env_file_paths() -> list[Path]:
    """Candidate .env locations for reading (writable path first)."""
    paths: list[Path] = []
    primary = primary_env_file_path()
    paths.append(primary)
    root = repo_root()
    data_root = resolve_data_root()
    for candidate in (root / ".env", data_root / ".env"):
        if candidate not in paths:
            paths.append(candidate)
    return paths


def resolve_public_bridge_host() -> str:
    candidates: list[str] = []

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            candidates.append(str(probe.getsockname()[0]))
    except OSError:
        pass

    try:
        hostname_candidates = socket.gethostbyname_ex(socket.gethostname())[2]
        candidates.extend(str(item) for item in hostname_candidates)
    except OSError:
        pass

    for candidate in candidates:
        if candidate.startswith("127.") or candidate.startswith("169.254."):
            continue
        return candidate

    return "127.0.0.1"


def default_bridge_base_url() -> str:
    configured = os.environ.get("BRIDGE_BASE_URL", "").strip()
    if configured and "127.0.0.1" not in configured and "localhost" not in configured.lower():
        return configured.rstrip("/")

    host = resolve_public_bridge_host()
    return f"http://{host}:{MOBILE_BRIDGE_PORT}"


def cache_root(data_root: Path | None = None) -> Path:
    return (data_root or resolve_data_root()) / "data" / "cache"


def profiles_root(data_root: Path | None = None) -> Path:
    return (data_root or resolve_data_root()) / "data" / "user_profiles"


def user_settings_root(data_root: Path | None = None) -> Path:
    return (data_root or resolve_data_root()) / "data" / "user_settings"


def custom_dropdowns_path(data_root: Path | None = None) -> Path:
    return user_settings_root(data_root) / "custom_dropdowns.json"


def session_database_path(data_root: Path | None = None) -> Path:
    return cache_root(data_root) / "session_store.db"


def logs_root(data_root: Path | None = None) -> Path:
    return (data_root or resolve_data_root()) / "logs"


def session_registry_path(data_root: Path | None = None) -> Path:
    configured = os.environ.get("SESSION_REGISTRY_PATH", "").strip()
    if configured:
        return Path(configured).resolve()
    return cache_root(data_root) / "session_registry.json"


def briefing_storage_path(data_root: Path | None = None) -> Path:
    configured = os.environ.get("BRIEFING_STORAGE_PATH", "").strip()
    if configured:
        return Path(configured).resolve()
    return cache_root(data_root) / "web_briefing_drafts.json"


def pairing_codes_path(data_root: Path | None = None) -> Path:
    return cache_root(data_root) / "pairing_codes.json"


def license_state_path(data_root: Path | None = None) -> Path:
    return cache_root(data_root) / "license_state.json"


def overlay_show_flag_path(data_root: Path | None = None) -> Path:
    return cache_root(data_root) / "overlay_show.flag"


def _decode_env_text(raw_bytes: bytes) -> str:
    """Decode .env bytes safely (handles UTF-8, UTF-16, and stray nulls)."""
    if not raw_bytes:
        return ""
    if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
        try:
            return raw_bytes.decode("utf-16")
        except UnicodeDecodeError:
            pass
    if b"\x00" in raw_bytes:
        try:
            return raw_bytes.decode("utf-16-le")
        except UnicodeDecodeError:
            raw_bytes = raw_bytes.replace(b"\x00", b"")
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _sanitize_env_pair(key: str, value: str) -> tuple[str, str]:
    key = key.replace("\x00", "").strip()
    value = value.replace("\x00", "").strip().strip('"').strip("'")
    return key, value


def load_env_file() -> None:
    """Load key=value pairs from .env in the project folder (USB-safe)."""
    for env_path in env_file_paths():
        if not env_path.is_file():
            continue
        try:
            raw_bytes = env_path.read_bytes()
            text = _decode_env_text(raw_bytes)
            repaired_lines: list[str] = []
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    if line.startswith("#") or not line:
                        repaired_lines.append(raw_line.rstrip("\r\n"))
                    continue
                key, _, value = line.partition("=")
                key, value = _sanitize_env_pair(key, value)
                if not key or "\x00" in key or "\x00" in value:
                    continue
                repaired_lines.append(f"{key}={value}")
                if key not in os.environ:
                    try:
                        os.environ[key] = value
                    except ValueError:
                        continue
            needs_repair = (
                raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff"))
                or b"\x00" in raw_bytes
            )
            if needs_repair and repaired_lines:
                try:
                    env_path.write_text(
                        "\n".join(repaired_lines).rstrip() + "\n",
                        encoding="utf-8",
                    )
                except OSError:
                    pass
        except OSError:
            continue


def configure_runtime_environment() -> Path:
    """Create writable dirs and set env vars used by Flask and the mobile bridge."""
    if is_portable_mode():
        os.environ.setdefault("CAREER_COPILOT_PORTABLE", "1")

    load_env_file()
    data_root = resolve_data_root()
    cache = cache_root(data_root)
    profiles = profiles_root(data_root)
    settings = user_settings_root(data_root)
    logs = logs_root(data_root)

    for directory in (cache, profiles, settings, logs):
        directory.mkdir(parents=True, exist_ok=True)

    env_template = repo_root() / ".env.example"
    if not env_template.is_file():
        env_template = Path(__file__).resolve().parent / ".env.example"
    env_target = primary_env_file_path()
    if env_template.is_file() and not env_target.is_file():
        try:
            env_target.parent.mkdir(parents=True, exist_ok=True)
            template_text = _decode_env_text(env_template.read_bytes())
            env_target.write_text(template_text, encoding="utf-8")
        except OSError:
            pass

    os.environ.setdefault("DATA_ROOT", str(data_root))
    os.environ.setdefault("SESSION_REGISTRY_PATH", str(session_registry_path(data_root)))
    os.environ.setdefault("BRIEFING_STORAGE_PATH", str(briefing_storage_path(data_root)))
    os.environ.setdefault("BRIEFING_PROFILES_ROOT", str(profiles))
    os.environ.setdefault("BRIDGE_BASE_URL", default_bridge_base_url())
    return session_registry_path(data_root)


def portable_status_payload() -> dict[str, str | bool]:
    root = repo_root()
    data_root = resolve_data_root()
    return {
        "portable_mode": is_portable_mode(),
        "repo_root": str(root),
        "data_root": str(data_root),
        "env_file": str(primary_env_file_path()),
        "all_data_in_project_folder": data_root.resolve() == root.resolve(),
    }
