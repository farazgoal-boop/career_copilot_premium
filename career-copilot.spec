# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

_BUILD_PYTHON_CANDIDATES = [
    Path('venv311/Scripts/python.exe'),
    Path('.venv/Scripts/python.exe'),
]
if not any(Path(sys.executable).resolve() == candidate.resolve() for candidate in _BUILD_PYTHON_CANDIDATES if candidate.exists()):
    print(
        f"Warning: build Python is {Path(sys.executable).resolve()}. "
        f"Recommended: venv311 or .venv on Python 3.11."
    )

qt_datas, qt_binaries, qt_hiddenimports = collect_all('PySide6')
shiboken_datas, shiboken_binaries, shiboken_hiddenimports = collect_all('shiboken6')

try:
    sounddevice_datas, sounddevice_binaries, sounddevice_hiddenimports = collect_all('sounddevice')
except Exception:
    sounddevice_datas, sounddevice_binaries, sounddevice_hiddenimports = [], [], []

try:
    speech_datas, speech_binaries, speech_hiddenimports = collect_all('speech_recognition')
except Exception:
    speech_datas, speech_binaries, speech_hiddenimports = [], [], []


a = Analysis(
    ['premium_launcher.py'],
    pathex=['.'],
    binaries=[
        *qt_binaries,
        *shiboken_binaries,
        *sounddevice_binaries,
        *speech_binaries,
    ],
    datas=[
        ('desktop_app', 'desktop_app'),
        ('web_app', 'web_app'),
        ('mobile_app/__init__.py', 'mobile_app'),
        ('mobile_app/live_bridge.py', 'mobile_app'),
        ('mobile_app/contracts.py', 'mobile_app'),
        ('mobile_app/android_native.py', 'mobile_app'),
        ('mobile_app/android_runtime.py', 'mobile_app'),
        ('mobile_app/runtime_bridge.py', 'mobile_app'),
        ('runtime_paths.py', '.'),
        ('premium_launcher.py', '.'),
        ('portable.flag', '.'),
        ('app_licensing.py', '.'),
        ('web_app/templates', 'web_app/templates'),
        ('web_app/static', 'web_app/static'),
        ('data/cache/.gitkeep', 'data/cache'),
        ('data/user_profiles/.gitkeep', 'data/user_profiles'),
        ('.env.example', '.'),
        ('installers/windows/assets/user_manual.html', 'docs'),
        ('docs/USER_MANUAL.html', 'docs'),
        *qt_datas,
        *shiboken_datas,
        *sounddevice_datas,
        *speech_datas,
    ],
    hiddenimports=[
        'flask',
        *collect_submodules('flask'),
        'cryptography',
        *collect_submodules('cryptography'),
        'qrcode',
        *collect_submodules('qrcode'),
        'PIL',
        *collect_submodules('PIL'),
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        *qt_hiddenimports,
        *shiboken_hiddenimports,
        'sounddevice',
        *sounddevice_hiddenimports,
        'speech_recognition',
        *collect_submodules('speech_recognition'),
        *speech_hiddenimports,
        'segno',
        *collect_submodules('segno'),
        'pdfminer',
        *collect_submodules('pdfminer'),
        'werkzeug',
        *collect_submodules('werkzeug'),
        'jinja2',
        *collect_submodules('jinja2'),
        'itsdangerous',
        *collect_submodules('itsdangerous'),
        'click',
        *collect_submodules('click'),
        'blinker',
        *collect_submodules('blinker'),
        'markupsafe',
        *collect_submodules('markupsafe'),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'whisper', 'tensorflow', 'matplotlib', 'notebook'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Career Copilot Premium',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='installers\\windows\\assets\\app_icon.ico',
    version='career-copilot-version.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Career Copilot Premium',
)
