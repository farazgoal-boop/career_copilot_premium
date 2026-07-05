# Career Copilot Premium

AI interview assistant desktop app. PySide6 (floating overlay) + Flask (local dashboard). $299 product.

## Version

- Current version: v1.0.9
- Git tags:
  - `v1.0.5` — macOS SSL cert fix
  - `v1.0.6` — activation/profile/sessions/mobile QR
  - `v1.0.8` — overlay error dialog, tray icon
  - `stable-backup-2026-07-06` — recovery point, do not delete

## Key files

- `premium_launcher.py` — entry point (starts Flask + mobile bridge + Qt overlay)
- `desktop_app/overlay.py` — floating overlay window (PySide6)
- `web_app/routes.py` — Flask API/dashboard routes
- `app_licensing.py` — activation / machine licensing
- `desktop_app/mistral_setup.py` — AI provider (Mistral/Ollama) config
- `desktop_app/audio_handler.py` — mic/call-audio capture (sounddevice)

## Current active task

**Phase 1**: adding browser-based mic capture + live transcript + session recording (WebRTC in the browser, no local installs needed). See prior diagnosis of the current flow before touching this — audio capture today is Python/desktop-side only (`desktop_app/audio_handler.py`), there is no browser mic code yet.

## Fix status

**FIXED:**
- Activation persistence
- Profile save
- Sessions table UI
- Mobile QR browser companion
- Ollama optional labels
- Audio platform text (BlackHole/Stereo Mix/PulseAudio)
- Single-instance reactivation (`premium_launcher.py`)
- System tray quit (`premium_launcher.py`)

**PENDING:**
- Mac overlay (PySide6 on Mac unreliable)
- System slowdown (no root cause found yet)

## Safety rules

- Always diagnose before changing anything.
- One feature at a time, git branch per feature.
- Never touch: SSL fix, backup tags, activation code generation logic, Playwright test suite.
- Always confirm with user before committing.

## Client delivery

- Mac: script-based zip (`DELIVER_TO_CLIENT/Mac/`)
- Windows: `CareerCopilotPremium_Setup_vX.X.X.exe`
- Both clients need re-activation after major updates.

## Before starting work

DO NOT start new work without reading this file.
