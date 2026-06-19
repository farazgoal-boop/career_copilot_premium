================================================================================
 CAREER COPILOT PREMIUM — USB PORTABLE QUICK START
================================================================================

Everything runs from THIS folder. Nothing is installed on the laptop.

FIRST TIME (on your build PC only)
  1. install_deps.bat
  2. BUILD_CLIENT_PACKAGE.bat
  3. Put your MISTRAL_API_KEY in .env (same folder as this file)

ON ANY LAPTOP (from USB)
  1. Double-click START_PREMIUM.bat
  2. Browser opens → complete onboarding once (name + resume)
  3. Click "Start Interview" on the dashboard
  4. In the overlay: type question → Enter → AI answer in ~3 seconds

FILES THAT MATTER
  START_PREMIUM.bat     — main launcher (use this)
  .env                  — your API keys (stay on USB)
  portable.flag         — keeps data inside this folder
  data\                 — sessions, profiles, cache (on USB)
  premium_launcher.py   — dashboard + overlay engine

NO PYTHON ON LAPTOP?
  Use the built EXE after BUILD_CLIENT_PACKAGE.bat:
    dist\windows-bundle\career-copilot.exe
  Or copy "ready to client\windows" to USB.

MOBILE PHONE
  Same Wi-Fi → dashboard → Link Device → enter code in mobile app.

SUPPORT
  docs\user_manual.html — full guide (Print to PDF from browser)

================================================================================
