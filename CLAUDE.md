# Career Copilot Premium

AI interview assistant desktop app. PySide6 (floating overlay) + Flask (local dashboard). $299 product.

## Version

- Current version: v1.0.9
- Git tags:
  - `v1.0.5` — macOS SSL cert fix
  - `v1.0.6` — activation/profile/sessions/mobile QR
  - `v1.0.8` — overlay error dialog, tray icon
  - `stable-backup-2026-07-06` — recovery point, do not delete
  - `phase1-complete-2026-07-07` — browser mic capture + live transcript + transcript export, 62/62 e2e tests passing, do not delete

## Key files

- `premium_launcher.py` — entry point (starts Flask + mobile bridge + Qt overlay)
- `desktop_app/overlay.py` — floating overlay window (PySide6)
- `web_app/routes.py` — Flask API/dashboard routes
- `app_licensing.py` — activation / machine licensing
- `desktop_app/mistral_setup.py` — AI provider (Mistral/Ollama) config
- `desktop_app/audio_handler.py` — mic/call-audio capture (sounddevice)
- `desktop_app/session_types.py` — session_type schema (`job_interview`/`client_presentation`/`product_demo`/`team_meeting`/`sales_call`) + label helpers
- `desktop_app/visual_context.py` — Visual Context Library (profile-scoped reference image storage)
- `desktop_app/session_recording.py` — continuous per-session `.webm` recording storage (session-scoped, not profile-scoped)
- `desktop_app/meeting_summary.py` — post-session summary + action items generation from `transcript_log` (Mistral, JSON mode)
- `web_app/templates/session_report.html` — post-session report page (`/session/<id>/report`)

## Current active task

**Phase 1 — COMPLETE** (tag `phase1-complete-2026-07-07`): browser-based mic capture (Web Speech API in `web_app/static/js/browser_mic.js`) + live transcript log (`desktop_app/live_listen.py` transcript_log, surfaced in `web_app/templates/live_session.html`) + text transcript export/download (`GET /api/session/<id>/transcript/export` in `web_app/routes.py`). Scope was text-only recording, no audio capture. All 62 Playwright e2e tests passing.

**Phase 2 — in progress**, on branch `feature/visual-context-meeting-intel`:

1. Visual Context Library — image upload + Mistral vision, wired into live-session answers. **Done.**
2. Session-type-aware content generation — `session_type` field + per-type strategy/answer generation. **Done.**
3. Continuous browser session recording — one `.webm` per session (Goal #3). **Done.**
4. Meeting summary + action items generated from `transcript_log` on session end (Goal #4). **Done.** Note: built from `transcript_log` only (questions heard + Mistral's suggested replies), not a verified two-way transcript — the user's own spoken words are never captured.
5. Post-session report page at `/session/<id>/report` (Goal #5, Step 2.12) — surfaces summary, action items, transcript, and recording playback; sessions list routes ended sessions here instead of `/live`. **Done.**

Next: not yet defined — confirm scope with user before starting new work.

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
