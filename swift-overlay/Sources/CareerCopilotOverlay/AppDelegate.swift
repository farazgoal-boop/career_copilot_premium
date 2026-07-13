import AppKit
import Foundation

class AppDelegate: NSObject, NSApplicationDelegate {
    var overlayWindow: OverlayWindow?
    var flaskClient = FlaskClient()
    var hotkeyManager = HotkeyManager()
    var statusItem: NSStatusItem?
    var isVisible = true

    func applicationDidFinishLaunching(_ notification: Notification) {
        print("[CareerCopilot Overlay] Starting...")

        overlayWindow = OverlayWindow()
        setUpStatusItem()

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

    // The app runs with .accessory activation policy (no dock icon, no menu
    // bar), which otherwise leaves no way for the user to quit it — this
    // status item is the only exit path besides Force Quit.
    func setUpStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        item.button?.image = NSImage(
            systemSymbolName: "bubble.left.and.bubble.right.fill",
            accessibilityDescription: "Career Copilot Premium"
        )

        let menu = NSMenu()
        menu.addItem(withTitle: "Open Dashboard", action: #selector(openDashboard), keyEquivalent: "")
        menu.addItem(withTitle: "Show Overlay", action: #selector(showOverlay), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit Career Copilot Premium", action: #selector(quit), keyEquivalent: "q")
        for menuItem in menu.items {
            menuItem.target = self
        }
        item.menu = menu
        statusItem = item
    }

    @objc func openDashboard() {
        NSWorkspace.shared.open(URL(string: flaskClient.baseURL)!)
    }

    @objc func showOverlay() {
        isVisible = true
        overlayWindow?.orderFrontRegardless()
    }

    @objc func quit() {
        NSApplication.shared.terminate(nil)
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
