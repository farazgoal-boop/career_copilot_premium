// Career Copilot Premium -- macOS overlay (Electron, experimental)
//
// Mac-only alternative to desktop_app/overlay.py's PySide6 window. Talks to
// the same Flask backend over plain HTTP/SSE -- no changes to web_app/ or
// the Python process required. See electron-overlay/overlay.js for the
// renderer-side session polling/SSE logic.
'use strict';

const path = require('path');
const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, shell } = require('electron');

let mainWindow = null;
let tray = null;

const WINDOW_WIDTH = 460;
const WINDOW_HEIGHT = 620;

// premium_launcher.py's dashboard port can float if 5000 is busy (see
// get_dashboard_port() in runtime_paths.py) -- Step 2 will pass the real
// port here when it spawns this process. Defaults to the common case.
const FLASK_BASE_URL = process.env.CCP_DASHBOARD_URL || 'http://127.0.0.1:5000';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    minWidth: 380,
    minHeight: 300,
    transparent: true,
    frame: false,
    resizable: true,
    fullscreenable: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'overlay.html'), {
    search: `base=${encodeURIComponent(FLASK_BASE_URL)}`,
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    // 'screen-saver' level + visibleOnFullScreen is what actually keeps this
    // above another app's fullscreen Space (Zoom/Meet/Teams) -- alwaysOnTop
    // alone is not enough on macOS. This is the Electron-native equivalent
    // of the NSWindow.collectionBehavior/setLevel: fix already shipped for
    // the PySide6 overlay in desktop_app/overlay.py.
    mainWindow.setAlwaysOnTop(true, 'screen-saver');
    mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  mainWindow.webContents.on('console-message', (_event, _level, message) => {
    console.log('[renderer]', message);
  });
}

function toggleOverlayVisibility() {
  if (!mainWindow) return;
  if (mainWindow.isVisible()) {
    mainWindow.hide();
  } else {
    mainWindow.show();
    mainWindow.setAlwaysOnTop(true, 'screen-saver');
    mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  }
}

function registerGlobalShortcuts() {
  const listenOk = globalShortcut.register('F2', () => {
    mainWindow?.webContents.send('hotkey:listen');
  });
  const toggleOk = globalShortcut.register('F3', toggleOverlayVisibility);
  if (!listenOk) console.error('[overlay] Failed to register global F2 shortcut.');
  if (!toggleOk) console.error('[overlay] Failed to register global F3 shortcut.');
}

function createTray() {
  // Requires a real icon asset -- placeholder path, not shipped in this
  // experimental scaffold. Guarded so a missing icon never blocks the
  // overlay window itself from working.
  try {
    tray = new Tray(path.join(__dirname, 'assets', 'trayTemplate.png'));
    const menu = Menu.buildFromTemplate([
      {
        label: 'Show Overlay',
        click: () => {
          mainWindow?.show();
          mainWindow?.setAlwaysOnTop(true, 'screen-saver');
        },
      },
      {
        label: 'Open Dashboard',
        click: () => shell.openExternal(FLASK_BASE_URL),
      },
      { type: 'separator' },
      { label: 'Quit Career Copilot Overlay', click: () => app.quit() },
    ]);
    tray.setContextMenu(menu);
    tray.setToolTip('Career Copilot Premium');
  } catch (error) {
    console.warn('[overlay] Tray icon unavailable, continuing without a tray:', error.message);
  }
}

ipcMain.on('overlay:hide', () => {
  mainWindow?.hide();
});

ipcMain.on('overlay:quit', () => {
  app.quit();
});

ipcMain.on('overlay:set-opacity', (_event, value) => {
  const clamped = Math.max(0.15, Math.min(Number(value) || 1, 1));
  mainWindow?.setOpacity(clamped);
});

app.whenReady().then(() => {
  createWindow();
  registerGlobalShortcuts();
  createTray();
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});

app.on('window-all-closed', () => {
  // Overlay hides rather than closes (see renderer's hide button + F3), but
  // guard anyway: don't quit the whole app just because the window closed,
  // mirroring the PySide6 overlay's closeEvent() behavior.
});
