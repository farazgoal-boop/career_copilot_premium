# Career Copilot Premium

Career Copilot Premium is a cross-platform AI interview copilot for guided preparation, live interview support, and post-interview review. The repository includes the desktop runtime, browser control room, mobile bridge, Android client paths, packaging scripts, and operational docs used to build and verify the product.

## Download Desktop App

Pre-built Mac/Linux installers are attached to **GitHub Releases** when you push a version tag (for example `v1.0.0`) and the `Build Mac and Linux Desktop Apps` workflow completes. Windows `Setup.exe` is still built locally with `BUILD_CLIENT_PACKAGE.bat`.

| Platform | Artifact | Install |
|----------|----------|---------|
| **Windows** | `CareerCopilotPremium_Setup_v1.0.0.exe` | Double-click the installer (built locally via `BUILD_CLIENT_PACKAGE.bat`) |
| **macOS** | `CareerCopilotPremium-mac.dmg` | Open the DMG, drag the app to Applications. First launch: **right-click → Open** to bypass Gatekeeper |
| **Linux (Debian/Ubuntu)** | `CareerCopilotPremium-linux.deb` | `sudo dpkg -i CareerCopilotPremium-linux.deb` then launch from the app menu |
| **Linux (any distro)** | `CareerCopilotPremium-linux.AppImage` | `chmod +x CareerCopilotPremium-linux.AppImage` then double-click or run from terminal |

**Android:** `CareerCopilotPremium.apk` — build with `scripts\build_apk.bat` on Windows; same APK works on all phones.

### Live Listen (F2) audio on Mac and Linux

VB-Cable is **Windows-only**. For call audio capture on other platforms:

- **macOS:** Install [BlackHole](https://existential.audio/blackhole/) (`brew install blackhole-2ch`) and route meeting audio through it. See `client_package/SETUP_GUIDE_MAC.txt`.
- **Linux:** Use PulseAudio loopback (`pactl load-module module-loopback`) or a virtual cable. See `client_package/SETUP_GUIDE_LINUX.txt`.

API keys and session data are stored in OS-appropriate user folders (not next to the app binary):

- Windows: `%LOCALAPPDATA%\CareerCopilotPremium\`
- macOS: `~/Library/Application Support/CareerCopilotPremium/`
- Linux: `~/.config/CareerCopilotPremium/` (or `$XDG_CONFIG_HOME/CareerCopilotPremium/`)

## Product flow

1. onboarding and profile training
2. pre-interview strategy generation
3. live interview assistance from desktop and browser controls
4. post-interview reporting and learning review

## Current scope

Implemented areas:

1. desktop onboarding, resume parsing, strategy generation, and report export
2. SQLite-backed session persistence with queued control commands and worker processing
3. Flask control room for session launch, pairing, and live action queueing
4. live mobile bridge with QR and deep-link pairing flows
5. React Native Android shell and Kivy prototype paths
6. Windows packaging, installer scripts, backup, and restore tooling

## Repository layout

- `desktop_app/`: desktop runtime, session orchestration, overlays, onboarding, reports
- `web_app/`: Flask app, templates, static assets, browser control room routes
- `mobile_app/`: live bridge, mobile contracts, Android runtime scaffolding, React Native app
- `scripts/`: setup, packaging, smoke validation, backup, restore, and release helpers
- `docs/`: operational docs, release checklists, backup and restore guidance, user guide

## Quick start

Windows setup:

```bat
scripts\setup.bat
```

Manual environment setup:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run the desktop baseline:

```bash
python -m desktop_app.main
```

Run the test suite:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

## Common workflows

Launch the real desktop runtime:

```bash
python -m desktop_app.main --desktop-runtime --profile-dir data/user_profiles/YOUR_PROFILE_DIR --company "Acme AI" --role "Staff Backend Engineer"
```

Start a session lifecycle:

```bash
python -m desktop_app.main --profile-dir data/user_profiles/amina-khan --company "Acme AI" --role "Staff Backend Engineer" --start-session
```

Queue and process session commands:

```bash
python -m desktop_app.main --session-id SESSION_ID --session-command toggle
python -m desktop_app.main --session-id SESSION_ID --process-session-commands
```

Run a short scripted session flow:

```bash
python -m desktop_app.main --profile-dir data/user_profiles/amina-khan --company "Acme AI" --role "Staff Backend Engineer" --session-script "toggle,toggle,fallback:emergency,status"
```

Launch the browser dashboard:

```bash
python -m web_app.app
```

Expose the browser dashboard through a public tunnel and let Flask generate tunnel-aware URLs:

```bash
set SERVER_NAME=https://career-copilot.ngrok.io
ngrok http 5000
```

For a fuller guide covering ngrok and Cloudflare Tunnel, see [docs/CUSTOM_DOMAIN.md](docs/CUSTOM_DOMAIN.md).

Serve the live mobile bridge:

```bash
python -m desktop_app.main --serve-mobile-bridge
```

Export a mobile bridge snapshot:

```bash
python -m desktop_app.main --export-mobile-bridge SESSION_ID --export-path mobile_bridge.json
```

## Packaging and mobile workflows

Build the Windows bundle:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_bundle.ps1
```

Start the quick mobile bridge launcher:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_mobile_bridge_quick.ps1
```

Start the pro-mode mobile launcher:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_mobile_pro_mode.ps1
```

Build the React Native Android release artifact:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\validate_mobile_release_env.ps1
powershell -ExecutionPolicy Bypass -File scripts\install_android_commandline_tools.ps1 -PersistEnvironment
powershell -ExecutionPolicy Bypass -File scripts\install_portable_gradle.ps1
powershell -ExecutionPolicy Bypass -File scripts\build_android_react_native.ps1
```

Configure local Android release signing:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\configure_android_release_signing.ps1 -StoreFile "C:\path\to\release.keystore" -KeyAlias "upload"
powershell -ExecutionPolicy Bypass -File scripts\validate_mobile_release_env.ps1
```

Create a restorable backup zip:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
```

Restore a backup into a fresh environment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -BackupZip .\backups\YOUR_BACKUP.zip
```

If Python is not available as `python`, the restore workflow also accepts an explicit interpreter path:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -BackupZip .\backups\YOUR_BACKUP.zip -PythonCommand "C:\Path\To\python.exe"
```

## Notes

- The desktop runtime uses SQLite as the source of truth for persisted session state and a file-backed command queue for cross-process control.
- The browser control room and mobile bridge are both intended to operate against the same live session data.
- Android flows are implemented in-repo, but final device-side validation and signed release distribution remain environment-dependent.

## Documentation

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md)
- [docs/MOBILE_RUNTIME.md](docs/MOBILE_RUNTIME.md)
- [docs/MOBILE_RELEASE_CHECKLIST.md](docs/MOBILE_RELEASE_CHECKLIST.md)
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- [docs/CUSTOM_DOMAIN.md](docs/CUSTOM_DOMAIN.md)