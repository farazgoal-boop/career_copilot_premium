[app]
title = Career Copilot Mobile
package.name = careercopilotmobile
package.domain = com.careercopilot
source.dir = .
source.include_exts = py,png,jpg,kv,json,md
version = 0.1.0
requirements = python3,kivy,pyjnius
orientation = portrait
fullscreen = 0
android.api = 34
android.minapi = 29
android.archs = arm64-v8a, armeabi-v7a
android.permissions = INTERNET,FOREGROUND_SERVICE,SYSTEM_ALERT_WINDOW,POST_NOTIFICATIONS,RECORD_AUDIO
services = bubble:mobile_app/kivy/service.py

[buildozer]
log_level = 2
warn_on_root = 1