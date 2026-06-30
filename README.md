# Career Copilot Premium

Career Copilot Premium is a cross-platform AI interview copilot with a live overlay, mobile phone pairing, and a browser-based control room. The desktop app handles real-time audio listening, AI answer generation, and session history — the browser UI provides the four-screen interface you interact with.

## UI Overview

The app has four main screens, all accessible from the collapsible sidebar:

| Screen | Purpose |
|--------|---------|
| **Home** | Start a new interview session; select role, company, and AI model |
| **Live Session** | Active interview view — real-time AI answer cards, topic chips, steer input |
| **Settings** | API keys (OpenAI, Mistral), audio device, theme, and overlay preferences |
| **Setup Wizard** | First-run onboarding — name, resume upload, API key, audio check |

**Sidebar sections:** Sessions · Profile · System Status · Link Device

## Overlay

The overlay is a compact floating window that stays on top during a live interview:

- **F3** — show / hide the overlay (global hotkey, works even when the app is in the background)
- **F2** — toggle live audio listening
- **Sidebar → "Open Overlay"** — alternative to F3 if you prefer not to use the keyboard
- Closing the overlay window **hides** it (does not destroy it) — F3 or the sidebar button brings it back

## Mobile Pairing

Link your phone to see live AI answers on your screen during an interview:

1. In the sidebar, click **Link Device**
2. Scan the QR code with your phone camera, or type the 6-digit pairing code manually
3. Your phone mirrors the live answer cards in real time

The same flow is accessible from **Settings → Link Device**.

## Download Desktop App

Pre-built Mac and Linux installers are attached to **GitHub Releases** when a version tag (`v*`) is pushed and the `Build Mac and Linux Desktop Apps` workflow completes.

| Platform | Artifact | Install |
|----------|----------|---------|
| **Windows** | `CareerCopilotPremium_Setup.exe` | Built locally via `BUILD_CLIENT_PACKAGE.bat` |
| **macOS** | `CareerCopilotPremium-mac.dmg` | Open the DMG, drag the app to Applications. First launch: **right-click → Open** to bypass Gatekeeper |
| **Linux (Debian/Ubuntu)** | `CareerCopilotPremium-linux.deb` | `sudo dpkg -i CareerCopilotPremium-linux.deb` then launch from the app menu |
| **Linux (any distro)** | `CareerCopilotPremium-linux.AppImage` | `chmod +x CareerCopilotPremium-linux.AppImage` then double-click or run from terminal |

### Live Listen (F2) audio on Mac and Linux

VB-Cable is **Windows-only**. For call audio capture on other platforms:

- **macOS:** Install [BlackHole](https://existential.audio/blackhole/) (`brew install blackhole-2ch`) and route meeting audio through it. See `client_package/SETUP_GUIDE_MAC.txt`.
- **Linux:** Use PulseAudio loopback (`pactl load-module module-loopback`) or a virtual cable. See `client_package/SETUP_GUIDE_LINUX.txt`.

API keys and session data are stored in OS-appropriate user folders (not next to the app binary):

- Windows: `%LOCALAPPDATA%\CareerCopilotPremium\`
- macOS: `~/Library/Application Support/CareerCopilotPremium/`
- Linux: `~/.config/CareerCopilotPremium/` (or `$XDG_CONFIG_HOME/CareerCopilotPremium/`)

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac / Linux
pip install -r requirements.txt
python start_app.py
```

The app opens your browser to `http://localhost:5000` automatically. If it doesn't, navigate there manually.

For development / test dependencies (Playwright e2e suite):

```bash
pip install -r requirements-dev.txt
py -m pytest tests/e2e/ -v
```

Windows one-liner setup:

```bat
scripts\setup.bat
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **F2** | Toggle live audio listening (global) |
| **F3** | Show / hide the overlay window (global) |

## Repository Layout

- `desktop_app/` — desktop runtime, session orchestration, overlay, hotkeys, onboarding
- `web_app/` — Flask app, Jinja templates, static CSS/JS, all browser-facing routes
- `mobile_app/` — live bridge, mobile contracts, Android runtime scaffolding
- `tests/e2e/` — Playwright end-to-end test suite (62 tests, 21 screenshots)
- `docs/` — user guide, install notes, backup/restore docs, deployment guide
- `scripts/` — setup, packaging, smoke validation, backup, restore, release helpers

## Packaging

Build the Mac / Linux installers by pushing a version tag:

```bash
git tag v1.0.x && git push origin v1.0.x
```

The `Build Mac and Linux Desktop Apps` GitHub Actions workflow produces the DMG, .deb, and AppImage automatically.

Build the Windows bundle locally:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_bundle.ps1
```

Create a restorable backup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
```

Restore from backup:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -BackupZip .\backups\YOUR_BACKUP.zip
```

## Notes

- The desktop runtime uses SQLite as the source of truth for session state and a file-backed command queue for cross-process control.
- The browser control room and mobile bridge both operate against the same live session data.
- The overlay window is persistent — closing it hides rather than destroys it, so hotkeys and the sidebar button can always bring it back.

## Documentation

- [docs/user-guide.html](docs/user-guide.html) — illustrated user guide with screenshots
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md)
- [docs/MOBILE_RUNTIME.md](docs/MOBILE_RUNTIME.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/CUSTOM_DOMAIN.md](docs/CUSTOM_DOMAIN.md)
