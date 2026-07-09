# Career Copilot Premium

AI interview assistant desktop app. PySide6 (floating overlay) + Flask (local dashboard). $299 product.

## Version

- Current version: v1.0.8 (latest published GitHub release — verified live against the API; a prior "v1.0.9" note here was inaccurate, no such tag/release exists). Also tracked as `CURRENT_APP_VERSION` in `web_app/routes.py` (used by the sidebar version badge + `/api/check-update`). Bump both together, plus `setup.py` / `career-copilot-version.txt`, when cutting a release (Phase 3 Step 3.10 will do this for v2.0.0).
- Git tags:
  - `v1.0.5` — macOS SSL cert fix
  - `v1.0.6` — activation/profile/sessions/mobile QR
  - `v1.0.8` — overlay error dialog, tray icon
  - `stable-backup-2026-07-06` — recovery point, do not delete
  - `phase1-complete-2026-07-07` — browser mic capture + live transcript + transcript export, 62/62 e2e tests passing, do not delete
  - `phase2-complete-2026-07-07` — Visual Context Library, session types, continuous recording, meeting summary, post-session report page. Merged to `main` (`--no-ff`), 62/62 e2e tests passing, do not delete

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
- `desktop_app/elevenlabs_setup.py` — ElevenLabs API key storage/validation (plaintext `.env`, mirrors `mistral_setup.py`)
- `desktop_app/voice_prefs.py` — voice/speed preferences for TTS
- `desktop_app/tts.py` — server-side ElevenLabs speech synthesis (key never reaches the browser)
- `desktop_app/language_config.py` — listen/reply/speak language prefs (extended in Phase 3 with `speak_language` + German)
- `desktop_app/translation.py` — Mistral-based translation, used only when "speak to caller in" differs from the answer's language
- `web_app/static/css/premium.css` — theme tokens (`:root` = dark default, `:root[data-theme="light"]` override); all new CSS must use these `--premium-*` vars
- `web_app/templates/_sidebar.html` — sidebar nav + version badge/update-check (bottom, revealed on hover/pin)

## Current active task

**Phase 1 — COMPLETE** (tag `phase1-complete-2026-07-07`): browser-based mic capture (Web Speech API in `web_app/static/js/browser_mic.js`) + live transcript log (`desktop_app/live_listen.py` transcript_log, surfaced in `web_app/templates/live_session.html`) + text transcript export/download (`GET /api/session/<id>/transcript/export` in `web_app/routes.py`). Scope was text-only recording, no audio capture. All 62 Playwright e2e tests passing.

**Phase 2 — COMPLETE** (tag `phase2-complete-2026-07-07`, merged to `main`, feature branch deleted):

1. Visual Context Library — image upload + Mistral vision, wired into live-session answers. **Done.**
2. Session-type-aware content generation — `session_type` field + per-type strategy/answer generation. **Done.**
3. Continuous browser session recording — one `.webm` per session (Goal #3). **Done.**
4. Meeting summary + action items generated from `transcript_log` on session end (Goal #4). **Done.** Note: built from `transcript_log` only (questions heard + Mistral's suggested replies), not a verified two-way transcript — the user's own spoken words are never captured.
5. Post-session report page at `/session/<id>/report` (Goal #5, Step 2.12) — surfaces summary, action items, transcript, and recording playback; sessions list routes ended sessions here instead of `/live`. **Done.**

**Phase 3 — IN PROGRESS**, branch `feature/multilang-premium-polish` (not merged to `main` yet). Goal: $299 → $999 tier, competing with Google Meet AI / Zoom AI Companion / Otter.ai. Ends in a v2.0.0 multi-platform build. 10 steps total; process is one step at a time, diff shown and confirmed before each commit, full Playwright suite run at least after Steps 3.3/3.7/3.9/3.10 (and as extra insurance after any step touching shared templates).

1. Real-time voice output (ElevenLabs + browser TTS fallback) — **Done** (commit `a7a1bafc`). Key stored plaintext `.env` like Mistral's. Speak button on live-session answers, Voice Output card in Settings, OS-aware VB-Cable/BlackHole guide on System Status.
2. Multi-language intelligence — **Done** (commit `6083a9f5`). Language Settings card (caller's language / answer language / speak-to-caller language, 8 languages). Speak button translates via Mistral when the target language differs from the answer's language.
3. Premium light/dark theme system — **Done** (commit `a5b4bfac`). `premium.css` token architecture (`--premium-*`, dark default + `[data-theme="light"]`), Appearance card in Settings, no-flash theme-init in `base.html`. `activation.html` deliberately excluded (own palette, never-touch per rules below).
4. Auto-update notification in sidebar — **Done** (commit `bb9e6a6c`). `GET /api/check-update` against the real GitHub Releases API, manual/click-triggered only.
5. Company/client research before sessions — **Done** (commit `ddbcd36f`). `desktop_app/company_research.py` (Mistral, JSON mode) generates an overview/focus-areas/culture-values/smart-questions briefing, auto-triggered from quick-start when a real company name is given (best-effort, never blocks session start) plus `GET/POST /api/session/<id>/research[/generate]`. Collapsible "Company research" card on `live_session.html`, "Add company details for research" modal on `index.html`. Briefing is LLM training-knowledge, not a live lookup — caveat surfaced in the UI.
6. Resume-matched personalized answers — **Done** (commit `1a6a83f8`). `strategy_generator.py`'s `build_resume_highlights()` flattens every skill/job-achievement/project (not just top-3/first) into keyword-tagged `ResumeHighlight`s on `StrategyPack`; `answer_builder.py` token-matches the live question against all of them and injects the most relevant specific experience into the prompt instead of always the same canned template.
7. Interview Preparation Mode (`/prepare`) — **Done** (commit `3fc09379`, 62/62 Playwright passing). New session-less page sourced from the saved briefing/profile: readiness score/band/action-plan (`ConfidenceAssessment`, first surfaced in UI here), full resume-highlight list (Step 3.6), on-demand company research via `POST /api/prepare/research` (session-less variant of Step 3.5), all 15 session-type practice questions as difficulty-grouped flashcards, and a "Start session now" CTA into quick-start. Sidebar link added in `_sidebar.html`.
8. Premium onboarding experience — **Done** (commit `17fb89e5`, 62/62 Playwright passing). Fixed a real substance bug: onboarding previously built the entire structured profile from hardcoded placeholders regardless of the uploaded resume, so Steps 3.6/3.7 worked off fake data for every real user. `desktop_app/resume_profile_extractor.py` (Mistral JSON-mode) now extracts real skills/work-history/projects from resume text, with a minimum-content check and clean fallback to the old placeholder path on any failure (missing key, sparse resume, LLM error — onboarding never blocks). Also added DOCX upload support (was PDF-only), drag-and-drop with filename confirmation, and a skills-preview chip list on the done step.
9. Performance + polish pass — **Done** (commit `30a8c136`, 62/62 Playwright passing). Signature shatter-out (8x6 grid, canvas/html2canvas capture) + 3D flip-in (rotateX/rotateY, easeOutBack overshoot) page transition, originating from the clicked sidebar item. `web_app/static/js/transition.js` (new, `CC_TRANSITION.runOut()` only — multi-page app, so the IN half animates the real `.page-content` directly on load, no capture needed). Wired into `_sidebar.html`'s nav click handler and `base.html`'s entry animation; `perspective`/reduced-motion rules in `premium.css`. Respects `prefers-reduced-motion` on both halves; degrades to a fast opacity fade if html2canvas fails to load (verified navigation is never blocked).
10. Final v2.0.0 build (version bump across `setup.py`/`career-copilot-version.txt`/installers, tag, multi-platform packages) — **Not started.** Run full Playwright suite after this step.

Never touch (Phase 3 additions, on top of the list below): `desktop_app/audio_handler.py`'s F2 path, Playwright test suite *structure*. If anything breaks mid-step: `git checkout -- <file>` and report, don't silently patch over it.

Resume prompt for a fresh session: "Read CLAUDE.md. Phase 3 in progress, Steps 3.1–3.9 done. We are at Step 3.10. Last commit `30a8c136`. Branch `feature/multilang-premium-polish`. Continue."

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
- Never touch: SSL fix, backup tags, activation code generation logic (including `activation.html`'s UI/palette), Playwright test suite structure, `desktop_app/audio_handler.py`'s F2 path.
- Always confirm with user before committing.

## Client delivery

- Mac: script-based zip (`DELIVER_TO_CLIENT/Mac/`)
- Windows: `CareerCopilotPremium_Setup_vX.X.X.exe`
- Both clients need re-activation after major updates.

## Before starting work

DO NOT start new work without reading this file.
