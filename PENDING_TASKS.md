# Career Copilot Premium — Task Status

## Completed (Priorities 1–8)

- **P1 First-time Mistral setup** — `desktop_app/mistral_setup.py` + blocking wizard in `premium_launcher.py` before Flask starts
- **P2 Overlay status bar** — API, audio, language lines in `desktop_app/overlay.py` with 5s refresh + startup ping
- **P3 Language selection** — Listen/Reply dropdowns in overlay; `desktop_app/language_config.py`; STT + Mistral prompt in `live_listen.py` / `answer_builder.py`
- **P4 EXE startup fixes** — `desktop_app/startup_utils.py`: splash, `logs/startup_error.log`, port 5000→5001 fallback, VC++ hint, error dialog
- **P5 Clean client ZIP** — `scripts/build_client_manifest.ps1` ships installer+APK+docs only (no full `windows/_internal`); `career-copilot.spec` excludes `react_native/node_modules`
- **P6 User manual** — `docs/USER_MANUAL.html` (print to PDF for USER_MANUAL.pdf)
- **P7 Mac/Linux** — `install_mac.sh`, `install_linux.sh`, `START_PREMIUM.sh`; `runtime_paths.py` uses `~/.career_copilot`
- **P8 Audio priority** — Stereo Mix → VB-Cable/BlackHole/Pulse → microphone in `audio_handler.py`

## Optional follow-ups

1. **Android first-launch API key UI** — Add Mistral key screen in `mobile_app/react_native/App.tsx` (desktop setup covers Windows today).
2. **Dashboard “Phone connected” badge** — Wire `GET /api/bridge/status` paired flag in `web_app/static/js/app.js`.
3. **USER_MANUAL.pdf** — Run `Ctrl+P` → Save as PDF from `docs/USER_MANUAL.html` and copy to `ready to client/docs/`.
4. **VirusTotal** — Upload `installer/CareerCopilotPremium_Setup_v1.0.0.exe`, paste link in `security/VIRUSTOTAL-LINK.txt`, rebuild ZIP.

## Rebuild commands

```bat
BUILD_CLIENT_PACKAGE.bat
scripts\build_apk.bat
```

## Seller activation

```bat
venv311\Scripts\python.exe scripts\generate_activation_code.py CCP-XXXX-XXXX-XXXX-XXXX-XXXX
```
