import AppKit
import Foundation

setbuf(stdout, nil) // print() is block-buffered when stdout isn't a terminal;
                     // without this, output written before a SIGTERM never reaches the log.

let app = NSApplication.shared
app.setActivationPolicy(.accessory) // No dock icon
let delegate = AppDelegate()
app.delegate = delegate
app.run()
