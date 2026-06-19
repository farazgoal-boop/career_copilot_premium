import {NativeModules, Platform} from 'react-native';

import {OverlayNativeStatus} from '../types';

type BubbleOverlayNativeModule = {
  getOverlayStatus: () => Promise<OverlayNativeStatus>;
  openOverlaySettings: () => Promise<string>;
  startBubbleOverlay: (baseUrl: string, sessionId: string) => Promise<string>;
  stopBubbleOverlay: () => Promise<string>;
  savePreferredConnection: (baseUrl: string, sessionId: string) => Promise<string>;
  getPreferredConnection: () => Promise<{baseUrl: string; sessionId: string}>;
  clearPreferredConnection: () => Promise<string>;
};

const nativeModule = NativeModules.BubbleOverlayModule as BubbleOverlayNativeModule | undefined;

export async function getOverlayStatus(): Promise<OverlayNativeStatus> {
  if (Platform.OS !== 'android' || !nativeModule) {
    return {
      available: false,
      canDrawOverlays: false,
      serviceRunning: false,
    };
  }
  return nativeModule.getOverlayStatus();
}

export async function openOverlaySettings(): Promise<string> {
  if (Platform.OS !== 'android' || !nativeModule) {
    return 'Android overlay settings are unavailable in this runtime.';
  }
  return nativeModule.openOverlaySettings();
}

export async function startBubbleOverlay(baseUrl: string, sessionId: string): Promise<string> {
  if (Platform.OS !== 'android' || !nativeModule) {
    return 'Native Android overlay service is unavailable in this runtime.';
  }
  return nativeModule.startBubbleOverlay(baseUrl, sessionId);
}

export async function stopBubbleOverlay(): Promise<string> {
  if (Platform.OS !== 'android' || !nativeModule) {
    return 'Native Android overlay service is unavailable in this runtime.';
  }
  return nativeModule.stopBubbleOverlay();
}

export async function savePreferredConnection(baseUrl: string, sessionId: string): Promise<string> {
  if (Platform.OS !== 'android' || !nativeModule) {
    return 'Native Android storage is unavailable in this runtime.';
  }
  return nativeModule.savePreferredConnection(baseUrl, sessionId);
}

export async function getPreferredConnection(): Promise<{baseUrl: string; sessionId: string}> {
  if (Platform.OS !== 'android' || !nativeModule) {
    return {baseUrl: '', sessionId: ''};
  }
  return nativeModule.getPreferredConnection();
}

export async function clearPreferredConnection(): Promise<string> {
  if (Platform.OS !== 'android' || !nativeModule) {
    return 'Native Android storage is unavailable in this runtime.';
  }
  return nativeModule.clearPreferredConnection();
}