import AppKit
import Foundation

let app = NSApplication.shared
app.setActivationPolicy(.accessory) // No dock icon
let delegate = AppDelegate()
app.delegate = delegate
app.run()
