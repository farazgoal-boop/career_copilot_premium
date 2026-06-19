"""Persistent editable dropdown helpers for the desktop Qt surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DEFAULT_DROPDOWN_OPTIONS: dict[str, list[str]] = {
    "work_modes": ["Remote", "Office", "Hybrid"],
    "skill_levels": ["Beginner", "Intermediate", "Expert"],
    "difficulty_levels": ["Junior", "Mid", "Senior", "Lead"],
    "industries": ["IT/Software", "Banking/Finance", "Healthcare", "Education", "E-commerce", "Manufacturing"],
    "company_types": ["Startup", "Corporate", "Agency", "Freelance"],
    "answer_styles": ["Simple English", "Professional", "Technical", "Balanced"],
    "response_tones": ["Confident", "Humble", "Energetic", "Calm"],
}

def default_dropdown_storage_path() -> Path:
    from runtime_paths import custom_dropdowns_path

    return custom_dropdowns_path()


def _normalize_option(value: str) -> str:
    return " ".join(str(value).split()).strip()


def _merge_options(defaults: Iterable[str], incoming: Iterable[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for option in [*defaults, *incoming]:
        normalized = _normalize_option(option)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


class CustomDropdownManager:
    def __init__(
        self,
        storage_path: str | Path | None = None,
        default_options: dict[str, list[str]] | None = None,
    ) -> None:
        self.storage_path = Path(storage_path) if storage_path else default_dropdown_storage_path()
        self.default_options = {
            key: list(values)
            for key, values in (default_options or DEFAULT_DROPDOWN_OPTIONS).items()
        }
        self._options = self._load_options()

    def _sanitize_payload(self, payload: object) -> dict[str, list[str]]:
        incoming = payload if isinstance(payload, dict) else {}
        sanitized: dict[str, list[str]] = {}
        for key, defaults in self.default_options.items():
            value = incoming.get(key, []) if isinstance(incoming, dict) else []
            items = value if isinstance(value, list) else []
            sanitized[key] = _merge_options(defaults, [str(item) for item in items])
        return sanitized

    def _ensure_writable_storage_path(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            probe = self.storage_path.parent / ".write_test"
            probe.touch()
            probe.unlink()
        except OSError:
            self.storage_path = default_dropdown_storage_path()
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_payload(self, payload: dict[str, list[str]]) -> None:
        self._ensure_writable_storage_path()
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load_options(self) -> dict[str, list[str]]:
        if not self.storage_path.exists():
            payload = self._sanitize_payload({})
            self._write_payload(payload)
            return payload

        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
            sanitized = self._sanitize_payload(payload)
            self._write_payload(sanitized)
            return sanitized

        return self._sanitize_payload(payload)

    def keys(self) -> list[str]:
        return list(self.default_options.keys())

    def get_options(self, field_key: str) -> list[str]:
        if field_key not in self._options:
            raise KeyError(f"Unknown dropdown field: {field_key}")
        return list(self._options[field_key])

    def add_custom_option(self, field_key: str, value: str) -> list[str]:
        if field_key not in self._options:
            raise KeyError(f"Unknown dropdown field: {field_key}")

        normalized = _normalize_option(value)
        if not normalized:
            return self.get_options(field_key)

        updated = _merge_options(self._options[field_key], [normalized])
        self._options[field_key] = updated
        self._write_payload(self._options)
        return list(updated)

    def as_dict(self) -> dict[str, list[str]]:
        return {key: list(values) for key, values in self._options.items()}


def load_dropdown_options(storage_path: str | Path | None = None) -> dict[str, list[str]]:
    return CustomDropdownManager(storage_path=storage_path).as_dict()


QT_IMPORT_ERROR: str | None = None

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QLabel,
        QLineEdit,
        QVBoxLayout,
    )

    QT_AVAILABLE = True
except ImportError as error:  # pragma: no cover - exercised in environments without Qt
    QT_IMPORT_ERROR = str(error)
    QT_AVAILABLE = False


if QT_AVAILABLE:
    class AddCustomValueDialog(QDialog):
        def __init__(self, title: str, initial_value: str = "", parent=None) -> None:
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setModal(True)

            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("Enter custom value:"))

            self.input = QLineEdit(initial_value)
            self.input.selectAll()
            layout.addWidget(self.input)

            buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
            ok_button = buttons.button(QDialogButtonBox.Ok)
            if ok_button is not None:
                ok_button.setText("Add")
            cancel_button = buttons.button(QDialogButtonBox.Cancel)
            if cancel_button is not None:
                cancel_button.setText("Cancel")
            buttons.accepted.connect(self._accept_if_valid)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

            self.input.returnPressed.connect(self._accept_if_valid)

        def _accept_if_valid(self) -> None:
            if _normalize_option(self.input.text()):
                self.accept()

        def value(self) -> str:
            return _normalize_option(self.input.text())


    class EditableComboBox(QComboBox):
        ADD_CUSTOM_TEXT = "+ Add custom..."

        def __init__(
            self,
            field_key: str,
            manager: CustomDropdownManager | None = None,
            placeholder: str = "Select or type a value",
            parent=None,
        ) -> None:
            super().__init__(parent)
            self.field_key = field_key
            self.manager = manager or CustomDropdownManager()
            self.setEditable(True)
            self.setInsertPolicy(QComboBox.NoInsert)
            self.setMinimumContentsLength(18)
            self.refresh_options()

            line_edit = self.lineEdit()
            if line_edit is not None:
                line_edit.setPlaceholderText(placeholder)
                line_edit.returnPressed.connect(self._handle_return_pressed)

            self.activated.connect(self._handle_activated)

        def refresh_options(self, selected_value: str | None = None) -> None:
            current_value = _normalize_option(selected_value or self.currentText())
            self.blockSignals(True)
            self.clear()
            options = self.manager.get_options(self.field_key)
            self.addItems(options)
            if options:
                self.insertSeparator(len(options))
            self.addItem(self.ADD_CUSTOM_TEXT)
            self.blockSignals(False)

            if current_value and current_value.casefold() != self.ADD_CUSTOM_TEXT.casefold():
                self.setCurrentText(current_value)
            elif options:
                self.setCurrentIndex(0)

        def prompt_for_custom_value(self, initial_value: str = "") -> str | None:
            dialog = AddCustomValueDialog("Add custom option", initial_value=initial_value, parent=self)
            if dialog.exec() != QDialog.Accepted:
                return None
            return dialog.value() or None

        def add_custom_value(self, value: str) -> str | None:
            normalized = _normalize_option(value)
            if not normalized:
                return None
            self.manager.add_custom_option(self.field_key, normalized)
            self.refresh_options(selected_value=normalized)
            return normalized

        def _handle_return_pressed(self) -> None:
            entered = _normalize_option(self.currentText())
            if not entered or entered.casefold() == self.ADD_CUSTOM_TEXT.casefold():
                return
            existing = {option.casefold() for option in self.manager.get_options(self.field_key)}
            if entered.casefold() in existing:
                self.setCurrentText(entered)
                return
            self.add_custom_value(entered)

        def _handle_activated(self, index: int) -> None:
            if index != self.count() - 1:
                return
            value = self.prompt_for_custom_value(self.lineEdit().text() if self.lineEdit() is not None else "")
            if value is None:
                self.refresh_options()
                return
            self.add_custom_value(value)
else:
    class EditableComboBox:  # type: ignore[no-redef]
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError(f"PySide6 is required for EditableComboBox: {QT_IMPORT_ERROR or 'Qt unavailable'}")