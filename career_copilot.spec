# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for macOS (.app + .dmg) and Linux (.deb / .AppImage) CI builds.

Windows continues to use career-copilot.spec via BUILD_CLIENT_PACKAGE.bat — do not replace that file.
"""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

import certifi
from PyInstaller.utils.hooks import collect_all, collect_submodules

IS_DARWIN = sys.platform == "darwin"

qt_datas, qt_binaries, qt_hiddenimports = collect_all("PySide6")
shiboken_datas, shiboken_binaries, shiboken_hiddenimports = collect_all("shiboken6")

try:
    sounddevice_datas, sounddevice_binaries, sounddevice_hiddenimports = collect_all("sounddevice")
except Exception:
    sounddevice_datas, sounddevice_binaries, sounddevice_hiddenimports = [], [], []

try:
    speech_datas, speech_binaries, speech_hiddenimports = collect_all("speech_recognition")
except Exception:
    speech_datas, speech_binaries, speech_hiddenimports = [], [], []


def _optional_icon_path() -> str | None:
    for candidate in (
        Path("assets/icon.icns"),
        Path("installers/windows/assets/app_icon.ico"),
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def _load_macos_info_plist() -> dict:
    plist_path = Path("macos/Info.plist")
    if plist_path.is_file():
        with plist_path.open("rb") as handle:
            return plistlib.load(handle)
    return {
        "CFBundleName": "Career Copilot Premium",
        "CFBundleDisplayName": "Career Copilot Premium",
        "CFBundleIdentifier": "com.farazautomation.careercopilotpremium",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleExecutable": "CareerCopilotPremium",
        "LSMinimumSystemVersion": "10.13",
        "NSMicrophoneUsageDescription": (
            "Career Copilot Premium needs microphone access to listen during your interview "
            "calls and generate AI-powered answer suggestions."
        ),
    }


def _optional_data(src: str, dest: str) -> tuple[str, str] | None:
    return (src, dest) if Path(src).is_file() else None


def _build_datas() -> list[tuple[str, str]]:
    required = [
        ("desktop_app", "desktop_app"),
        ("web_app", "web_app"),
        ("mobile_app/__init__.py", "mobile_app"),
        ("mobile_app/live_bridge.py", "mobile_app"),
        ("mobile_app/contracts.py", "mobile_app"),
        ("mobile_app/android_native.py", "mobile_app"),
        ("mobile_app/android_runtime.py", "mobile_app"),
        ("mobile_app/runtime_bridge.py", "mobile_app"),
        ("runtime_paths.py", "."),
        ("premium_launcher.py", "."),
        ("app_licensing.py", "."),
        ("web_app/templates", "web_app/templates"),
        ("web_app/static", "web_app/static"),
    ]
    optional = [
        ("data/cache/.gitkeep", "data/cache"),
        ("data/user_profiles/.gitkeep", "data/user_profiles"),
        (".env.example", "."),
        ("installers/windows/assets/user_manual.html", "docs"),
        ("docs/USER_MANUAL.html", "docs"),
    ]
    datas: list[tuple[str, str]] = []
    for src, dest in required:
        if not Path(src).exists():
            raise FileNotFoundError(f"Required PyInstaller data path missing: {src}")
        datas.append((src, dest))
    for src, dest in optional:
        entry = _optional_data(src, dest)
        if entry is not None:
            datas.append(entry)
    datas.append((certifi.where(), "certifi"))
    datas.extend(qt_datas)
    datas.extend(shiboken_datas)
    datas.extend(sounddevice_datas)
    datas.extend(speech_datas)
    return datas


a = Analysis(
    ["premium_launcher.py"],
    pathex=["."],
    binaries=[
        *qt_binaries,
        *shiboken_binaries,
        *sounddevice_binaries,
        *speech_binaries,
    ],
    datas=_build_datas(),
    hiddenimports=[
        "flask",
        *collect_submodules("flask"),
        "certifi",
        "cryptography",
        *collect_submodules("cryptography"),
        "qrcode",
        *collect_submodules("qrcode"),
        "PIL",
        *collect_submodules("PIL"),
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        *qt_hiddenimports,
        *shiboken_hiddenimports,
        "sounddevice",
        *sounddevice_hiddenimports,
        "speech_recognition",
        *collect_submodules("speech_recognition"),
        *speech_hiddenimports,
        "segno",
        *collect_submodules("segno"),
        "pdfminer",
        *collect_submodules("pdfminer"),
        "werkzeug",
        *collect_submodules("werkzeug"),
        "jinja2",
        *collect_submodules("jinja2"),
        "itsdangerous",
        *collect_submodules("itsdangerous"),
        "click",
        *collect_submodules("click"),
        "blinker",
        *collect_submodules("blinker"),
        "markupsafe",
        *collect_submodules("markupsafe"),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "whisper", "tensorflow", "matplotlib", "notebook"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CareerCopilotPremium",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=IS_DARWIN,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_optional_icon_path(),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CareerCopilotPremium",
)

if IS_DARWIN:
    app = BUNDLE(
        coll,
        name="CareerCopilotPremium.app",
        icon=_optional_icon_path(),
        bundle_identifier="com.farazautomation.careercopilotpremium",
        info_plist=_load_macos_info_plist(),
    )
