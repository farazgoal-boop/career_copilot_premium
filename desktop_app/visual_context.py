"""Visual Context Library: per-profile uploaded images analyzed via Mistral vision (Pixtral).

Images are described once at upload time and cached in the manifest, so live
sessions can reference them via the cheap text-only model without a per-turn
vision round-trip.
"""

from __future__ import annotations

from datetime import datetime, timezone
import base64
import json
import uuid
from pathlib import Path
from urllib import error, request

from .config_manager import ModelConfig, load_runtime_config
from .mistral_setup import mistral_api_key

MANIFEST_FILENAME = "visual_context.json"
IMAGES_DIRNAME = "visual_context"

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES_PER_PROFILE = 20

_MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}

VISION_DESCRIPTION_PROMPT = (
    "Describe this image factually for use as reference context during a live "
    "conversation. Mention any visible text, numbers, diagrams, charts, product "
    "names, or UI elements. Keep it under 120 words."
)


class ImageValidationError(ValueError):
    """Raised when an uploaded image fails validation."""


def visual_context_images_dir(profile_directory: Path) -> Path:
    return profile_directory / IMAGES_DIRNAME


def visual_context_manifest_path(profile_directory: Path) -> Path:
    return profile_directory / MANIFEST_FILENAME


def load_visual_context_manifest(profile_directory: Path) -> list[dict[str, object]]:
    manifest_path = visual_context_manifest_path(profile_directory)
    if not manifest_path.exists():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(payload.get("images", [])) if isinstance(payload, dict) else []


def find_image_entry(profile_directory: Path, image_id: str) -> dict[str, object] | None:
    for entry in load_visual_context_manifest(profile_directory):
        if str(entry.get("id")) == image_id:
            return entry
    return None


def _save_visual_context_manifest(profile_directory: Path, entries: list[dict[str, object]]) -> None:
    manifest_path = visual_context_manifest_path(profile_directory)
    manifest_path.write_text(json.dumps({"images": entries}, indent=2), encoding="utf-8")


def extension_for_filename(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_image_upload(filename: str, size_bytes: int) -> str:
    """Validate an upload and return its normalized lowercase extension, or raise ImageValidationError."""
    ext = extension_for_filename(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(
            f"Unsupported file type '.{ext or '?'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    if size_bytes <= 0:
        raise ImageValidationError("Uploaded file is empty.")
    if size_bytes > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            f"Image is too large ({size_bytes / 1_048_576:.1f} MB). Max size is {MAX_IMAGE_BYTES // 1_048_576} MB."
        )
    return ext


def describe_image_with_vision(
    image_bytes: bytes,
    mime_type: str,
    model_config: ModelConfig | None = None,
    timeout_seconds: float = 20.0,
) -> str:
    """Call Mistral's vision model (Pixtral) to describe an image. Raises on failure."""
    config = model_config or load_runtime_config().model
    api_key = mistral_api_key()
    if not api_key:
        raise RuntimeError("Mistral API key is not configured — add one in Settings.")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": config.vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_DESCRIPTION_PROMPT},
                    {"type": "image_url", "image_url": f"data:{mime_type};base64,{encoded}"},
                ],
            }
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        config.vision_base_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as http_error:
        raise RuntimeError(f"Mistral vision API error ({http_error.code}).") from http_error
    except (OSError, TimeoutError, ValueError, error.URLError) as exc:
        raise RuntimeError(f"Could not reach Mistral vision API: {exc}") from exc

    choices = response_payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Mistral vision response did not include choices.")
    message = choices[0].get("message", {})
    description = str(message.get("content", "")).strip()
    if not description:
        raise RuntimeError("Mistral vision response did not include a description.")
    return description


def add_visual_context_image(
    profile_directory: Path,
    filename: str,
    file_bytes: bytes,
    model_config: ModelConfig | None = None,
) -> dict[str, object]:
    """Validate, store, and describe an uploaded image. Enforces the per-profile image cap."""
    ext = validate_image_upload(filename, len(file_bytes))
    mime_type = _MIME_TYPES[ext]

    images_dir = visual_context_images_dir(profile_directory)
    images_dir.mkdir(parents=True, exist_ok=True)

    image_id = uuid.uuid4().hex
    stored_filename = f"{image_id}.{ext}"
    (images_dir / stored_filename).write_bytes(file_bytes)

    try:
        description = describe_image_with_vision(file_bytes, mime_type, model_config)
        description_error = ""
    except Exception as exc:  # noqa: BLE001 - keep the image even if vision fails
        description = ""
        description_error = str(exc)

    entry: dict[str, object] = {
        "id": image_id,
        "filename": filename,
        "stored_filename": stored_filename,
        "mime_type": mime_type,
        "description": description,
        "description_error": description_error,
        "uploaded_at": _utc_now_iso(),
    }

    entries = load_visual_context_manifest(profile_directory)
    entries.append(entry)
    entries = _enforce_image_cap(profile_directory, entries)
    _save_visual_context_manifest(profile_directory, entries)
    return entry


def _enforce_image_cap(profile_directory: Path, entries: list[dict[str, object]]) -> list[dict[str, object]]:
    if len(entries) <= MAX_IMAGES_PER_PROFILE:
        return entries
    overflow = len(entries) - MAX_IMAGES_PER_PROFILE
    oldest, remaining = entries[:overflow], entries[overflow:]
    images_dir = visual_context_images_dir(profile_directory)
    for old_entry in oldest:
        stored_filename = str(old_entry.get("stored_filename", "") or "")
        if stored_filename:
            (images_dir / stored_filename).unlink(missing_ok=True)
    return remaining


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
