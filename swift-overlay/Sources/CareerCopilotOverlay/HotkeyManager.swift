import Carbon
import Foundation

class HotkeyManager {
    var onF2: (() -> Void)?
    var onF3: (() -> Void)?

    private var f2HotkeyRef: EventHotKeyRef?
    private var f3HotkeyRef: EventHotKeyRef?

    func register() {
        var eventSpec = [
            EventTypeSpec(eventClass: OSType(kEventClassKeyboard),
                         eventKind: UInt32(kEventHotKeyPressed))
        ]

        InstallEventHandler(
            GetApplicationEventTarget(),
            { (_, event, userData) -> OSStatus in
                guard let userData = userData, let event = event else { return noErr }
                let manager = Unmanaged<HotkeyManager>
                    .fromOpaque(userData).takeUnretainedValue()

                var hotkeyID = EventHotKeyID()
                GetEventParameter(event,
                    EventParamName(kEventParamDirectObject),
                    EventParamType(typeEventHotKeyID),
                    nil, MemoryLayout<EventHotKeyID>.size,
                    nil, &hotkeyID)

                DispatchQueue.main.async {
                    if hotkeyID.id == 1 { manager.onF2?() }
                    if hotkeyID.id == 2 { manager.onF3?() }
                }
                return noErr
            },
            1, &eventSpec,
            Unmanaged.passUnretained(self).toOpaque(),
            nil
        )

        // Register F2 (keyCode 120)
        var f2ID = EventHotKeyID(signature: OSType(0x4343), id: 1)
        RegisterEventHotKey(120, 0, f2ID,
                           GetApplicationEventTarget(), 0, &f2HotkeyRef)

        // Register F3 (keyCode 99)
        var f3ID = EventHotKeyID(signature: OSType(0x4343), id: 2)
        RegisterEventHotKey(99, 0, f3ID,
                           GetApplicationEventTarget(), 0, &f3HotkeyRef)

        print("[Overlay] F2/F3 hotkeys registered via Carbon")
    }
}
