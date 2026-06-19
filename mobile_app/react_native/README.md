# React Native Mobile Shell

This React Native shell now targets the live mobile bridge HTTP API exposed by `python -m desktop_app.main --serve-mobile-bridge`.

Implemented surfaces:

1. `App.tsx` for a live session dashboard and control surface.
2. `src/api/liveBridge.ts` for polling the shared bridge contract and posting actions.
3. `src/native/BubbleOverlayModule.ts` for Android overlay settings plus foreground overlay service control.
4. `android/.../BubbleOverlayService.kt` for the native floating bubble overlay backed by the live bridge.

Expected Android wiring:

1. Add `BubbleOverlayPackage()` to the React Native package list in the Android host app.
2. Request overlay permission before starting the overlay service.
3. Start the desktop-side live bridge, then point the app at `http://YOUR_HOST:8765` and the target session ID.

The shared payload still uses the `desktop_session_store_v1` schema, now wrapped in a live HTTP transport envelope.