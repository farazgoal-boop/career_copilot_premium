import AppKit

class OverlayWindow: NSPanel {

    init() {
        super.init(
            contentRect: NSRect(x: 20, y: 400,
                               width: 400, height: 300),
            styleMask: [.nonactivatingPanel,
                       .fullSizeContentView,
                       .borderless],
            backing: .buffered,
            defer: false
        )

        // ALWAYS on top — above EVERYTHING including fullscreen
        self.level = NSWindow.Level(
            rawValue: Int(CGWindowLevelForKey(.maximumWindow)) - 1
        )

        // Visible on ALL spaces/workspaces
        self.collectionBehavior = [
            .canJoinAllSpaces,
            .stationary,
            .fullScreenAuxiliary
        ]

        // Transparent background
        self.isOpaque = false
        self.backgroundColor = NSColor.clear
        self.hasShadow = true

        // Ignore mouse on transparent areas
        self.ignoresMouseEvents = false
        self.acceptsMouseMovedEvents = true

        // Keep on screen
        self.isReleasedWhenClosed = false

        // Setup content
        let contentVC = OverlayViewController()
        self.contentViewController = contentVC

        // Show immediately
        self.orderFrontRegardless()
    }

    // Window stays on top even when other apps focused
    override var canBecomeKey: Bool { return true }
    override var canBecomeMain: Bool { return false }
}
