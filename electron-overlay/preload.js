const { contextBridge, ipcRenderer, clipboard } = require('electron');

contextBridge.exposeInMainWorld('overlayAPI', {
  hide: () => ipcRenderer.send('overlay:hide'),
  quit: () => ipcRenderer.send('overlay:quit'),
  copyText: (text) => clipboard.writeText(text),
  setOpacity: (value) => ipcRenderer.send('overlay:set-opacity', value),
  onHotkeyListen: (callback) => ipcRenderer.on('hotkey:listen', () => callback()),
});
