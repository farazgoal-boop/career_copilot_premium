import AppKit

class AppDelegate: NSObject, NSApplicationDelegate {
    var overlayWindow: OverlayWindow?
    var flaskClient = FlaskClient()
    var hotkeyManager = HotkeyManager()
    var isVisible = true

    func applicationDidFinishLaunching(_ notification: Notification) {
        print("[CareerCopilot Overlay] Starting...")

        overlayWindow = OverlayWindow()

        flaskClient.onAnswerReceived = { [weak self] answer in
            (self?.overlayWindow?.contentViewController
             as? OverlayViewController)?.updateAnswer(answer)
        }
        flaskClient.startPolling()

        hotkeyManager.onF2 = { [weak self] in
            print("[Overlay] F2 pressed — triggering listen")
            self?.flaskClient.triggerListen()
        }
        hotkeyManager.onF3 = { [weak self] in
            print("[Overlay] F3 pressed — toggling visibility")
            self?.toggleVisibility()
        }
        hotkeyManager.register()

        print("[CareerCopilot Overlay] Ready!")
    }

    func toggleVisibility() {
        isVisible.toggle()
        if isVisible {
            overlayWindow?.orderFrontRegardless()
        } else {
            overlayWindow?.orderOut(nil)
        }
    }
}
