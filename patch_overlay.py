content = open("desktop_app/overlay.py", encoding="utf-8").read()
old1 = """def create_overlay_controller(theme="dark", initial_state=None):
    state = initial_state or build_preview_overlay_state()
    if not QT_AVAILABLE or QApplication is None or QApplication.instance() is None:
        return LiveOverlayController(initial_state=state)
    return LiveOverlayController(TransparentOverlayWindow(state), initial_state=state)"""
new1 = """def create_overlay_controller(theme="dark", initial_state=None):
    state = initial_state or build_preview_overlay_state()
    return LiveOverlayController(initial_state=state)"""
print("Fix1 found:", old1 in content)
if old1 in content:
    content = content.replace(old1, new1)
    open("desktop_app/overlay.py", "w", encoding="utf-8").write(content)
    print("Fixed!")
