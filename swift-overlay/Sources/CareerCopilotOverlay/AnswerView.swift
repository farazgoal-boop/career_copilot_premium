import AppKit

class OverlayViewController: NSViewController {

    private let background = NSVisualEffectView()
    private let textView = NSTextView()

    override func loadView() {
        let container = NSView(frame: NSRect(x: 0, y: 0, width: 400, height: 300))
        container.wantsLayer = true

        background.frame = container.bounds
        background.autoresizingMask = [.width, .height]
        background.material = .hudWindow
        background.state = .active
        background.wantsLayer = true
        background.layer?.cornerRadius = 14
        background.layer?.masksToBounds = true
        container.addSubview(background)

        textView.frame = container.bounds.insetBy(dx: 16, dy: 16)
        textView.autoresizingMask = [.width, .height]
        textView.isEditable = false
        textView.isSelectable = true
        textView.drawsBackground = false
        textView.textColor = .labelColor
        textView.font = NSFont.systemFont(ofSize: 14)
        textView.string = "Waiting for a question…"
        background.addSubview(textView)

        self.view = container
    }

    func updateAnswer(_ answer: String) {
        textView.string = answer
    }
}
