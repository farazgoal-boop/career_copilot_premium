import React, {useEffect, useState} from 'react';
import {
  ActivityIndicator,
  Linking,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {Camera, CameraType} from 'react-native-camera-kit';

import {BubbleCard} from './src/components/BubbleCard';
import {PermissionBanner} from './src/components/PermissionBanner';
import {SessionActionGrid} from './src/components/SessionActionGrid';
import {StatusHeader} from './src/components/StatusHeader';
import {bootstrapLiveSession, confirmLiveBridgePairingCode, fetchLiveBridgeHealth, fetchLiveBridgeSessions} from './src/api/liveBridge';
import {useLiveBridge} from './src/hooks/useLiveBridge';
import {SessionSummary} from './src/types';
import {
  getOverlayStatus,
  startBubbleOverlay,
  stopBubbleOverlay,
} from './src/native/BubbleOverlayModule';

const DEFAULT_BASE_URL = '';
const BRIDGE_URL_STORAGE_KEY = 'BRIDGE_URL';
const BRIDGE_SESSION_STORAGE_KEY = 'BRIDGE_SESSION_ID';

function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, '');
  if (!trimmed) {
    return '';
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `http://${trimmed}`;
}

function isLocalhostBridgeUrl(value: string): boolean {
  return /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(value);
}

function parseDeepLinkConnection(urlValue: string): {baseUrl: string; sessionId: string; pairingCode: string} | null {
  try {
    const parsed = new URL(urlValue);
    if (parsed.protocol === 'careercopilot:' && parsed.hostname === 'connect') {
      const baseUrl = normalizeBaseUrl(
        parsed.searchParams.get('baseUrl') || parsed.searchParams.get('bridgeUrl') || '',
      );
      const sessionId = (parsed.searchParams.get('sessionId') || '').trim();
      const pairingCode = (parsed.searchParams.get('pairingCode') || '')
        .replace(/\D+/g, '')
        .slice(0, 6);
      if (!baseUrl && !sessionId && !pairingCode) {
        return null;
      }
      return {baseUrl, sessionId, pairingCode};
    }

    // Backward-compatible parsing for older QR URLs like /mobile/connect?code=123456
    // and the current LAN bridge QR format /pairing/confirm?pairingCode=123456.
    if (
      /^https?:$/i.test(parsed.protocol) &&
      (parsed.pathname === '/mobile/connect' || parsed.pathname === '/pairing/confirm')
    ) {
      const pairingCode = (
        parsed.searchParams.get('pairingCode') || parsed.searchParams.get('code') || ''
      ).replace(/\D+/g, '').slice(0, 6);
      const baseUrl = normalizeBaseUrl(parsed.searchParams.get('bridgeUrl') || `${parsed.origin}`);
      if (!pairingCode) {
        return null;
      }
      return {baseUrl, sessionId: '', pairingCode};
    }

    return null;
  } catch {
    return null;
  }
}

function extractScannedPairingCode(rawValue: string): string {
  const value = String(rawValue || '').trim();
  if (!value) {
    return '';
  }

  if (/^\d{6}$/.test(value)) {
    return value;
  }

  const labeledMatch = value.match(/(?:^|\b)(?:pairing\s*code|code)\s*[:=#-]?\s*(\d{6})(?:\b|$)/i);
  if (labeledMatch) {
    return labeledMatch[1];
  }

  const queryMatch = value.match(/(?:[?&]|\b)(?:pairingCode|code)=(\d{6})(?:\b|&|$)/i);
  if (queryMatch) {
    return queryMatch[1];
  }

  return '';
}

async function probeBridgeHealth(candidateBaseUrl: string): Promise<boolean> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    controller.abort();
  }, 1800);

  try {
    const response = await fetch(`${candidateBaseUrl.replace(/\/+$/, '')}/health`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      return false;
    }
    const payload = (await response.json()) as {ok?: boolean};
    return Boolean(payload.ok);
  } catch {
    return false;
  } finally {
    clearTimeout(timeoutId);
  }
}

function buildDiscoveryCandidates(currentBaseUrl: string): string[] {
  const normalized = normalizeBaseUrl(currentBaseUrl);
  const candidates: string[] = [];
  const port = '8765';

  if (normalized) {
    try {
      const parsed = new URL(normalized);
      const host = parsed.hostname;
      const resolvedPort = parsed.port || port;
      const octets = host.split('.');
      if (octets.length === 4 && octets.every(item => /^\d+$/.test(item))) {
        const prefix = `${octets[0]}.${octets[1]}.${octets[2]}`;
        for (let i = 2; i <= 254; i += 1) {
          const candidateHost = `${prefix}.${i}`;
          if (candidateHost === host) {
            continue;
          }
          candidates.push(`http://${candidateHost}:${resolvedPort}`);
        }
      }
    } catch {
      // Fall through to common LAN prefixes.
    }
  }

  if (candidates.length === 0) {
    const commonPrefixes = ['192.168.0', '192.168.1', '192.168.100', '10.0.0'];
    for (const prefix of commonPrefixes) {
      for (let i = 2; i <= 40; i += 1) {
        candidates.push(`http://${prefix}.${i}:${port}`);
      }
    }
  }

  return candidates;
}

async function loadSavedBridgeSettings(): Promise<{baseUrl: string; sessionId: string}> {
  try {
    const [baseUrl, sessionId] = await Promise.all([
      AsyncStorage.getItem(BRIDGE_URL_STORAGE_KEY),
      AsyncStorage.getItem(BRIDGE_SESSION_STORAGE_KEY),
    ]);
    return {
      baseUrl: normalizeBaseUrl(baseUrl || ''),
      sessionId: (sessionId || '').trim(),
    };
  } catch {
    return {baseUrl: '', sessionId: ''};
  }
}

async function saveBridgeSettings(baseUrl: string, sessionId: string): Promise<void> {
  const normalizedUrl = normalizeBaseUrl(baseUrl);
  const normalizedSessionId = sessionId.trim();

  if (!normalizedUrl || isLocalhostBridgeUrl(normalizedUrl)) {
    await AsyncStorage.multiRemove([BRIDGE_URL_STORAGE_KEY, BRIDGE_SESSION_STORAGE_KEY]);
    return;
  }

  await AsyncStorage.multiSet([
    [BRIDGE_URL_STORAGE_KEY, normalizedUrl],
    [BRIDGE_SESSION_STORAGE_KEY, normalizedSessionId],
  ]);
}

export default function App(): React.JSX.Element {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [bridgeUrlInput, setBridgeUrlInput] = useState(DEFAULT_BASE_URL);
  const [sessionId, setSessionId] = useState('');
  const [availableSessions, setAvailableSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [bootstrapLoading, setBootstrapLoading] = useState(false);
  const [autoFixLoading, setAutoFixLoading] = useState(false);
  const [findDesktopLoading, setFindDesktopLoading] = useState(false);
  const [linkDeviceLoading, setLinkDeviceLoading] = useState(false);
  const [saveConnectLoading, setSaveConnectLoading] = useState(false);
  const [pairingCode, setPairingCode] = useState('');
  const [savedBridgeHydrated, setSavedBridgeHydrated] = useState(false);
  const [startupDiscoveryComplete, setStartupDiscoveryComplete] = useState(false);
  const [scannerVisible, setScannerVisible] = useState(false);
  const [scannerLastReadAt, setScannerLastReadAt] = useState(0);
  const [desktopReachable, setDesktopReachable] = useState<boolean | null>(null);
  const [overlayMessage, setOverlayMessage] = useState('Android overlay idle.');
  const [overlayRunning, setOverlayRunning] = useState(false);

  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
  const normalizedSessionId = sessionId.trim();
  const usingLocalhostBridge = isLocalhostBridgeUrl(normalizedBaseUrl);
  const bridgeReady = normalizedBaseUrl.length > 0 && normalizedSessionId.length > 0 && !usingLocalhostBridge;

  const {data, error, loading, refresh, triggerAction} = useLiveBridge({
    baseUrl: normalizedBaseUrl,
    sessionId: normalizedSessionId,
    enabled: bridgeReady,
  });

  const persistPreferredConnection = async (urlValue: string, sessionValue: string) => {
    const normalizedUrl = normalizeBaseUrl(urlValue);
    if (!normalizedUrl || isLocalhostBridgeUrl(normalizedUrl)) {
      return;
    }
    await saveBridgeSettings(normalizedUrl, sessionValue.trim());
  };

  const resolveReachableDesktop = async (candidateUrl: string) => {
    const normalizedCandidateUrl = normalizeBaseUrl(candidateUrl);

    if (normalizedCandidateUrl && !isLocalhostBridgeUrl(normalizedCandidateUrl)) {
      const directHit = await probeBridgeHealth(normalizedCandidateUrl);
      if (directHit) {
        return normalizedCandidateUrl;
      }
    }

    const candidates = buildDiscoveryCandidates(normalizedCandidateUrl);
    const batchSize = 14;

    for (let i = 0; i < candidates.length; i += batchSize) {
      const batch = candidates.slice(i, i + batchSize);
      const checks = await Promise.all(batch.map(async item => ({candidate: item, ok: await probeBridgeHealth(item)})));
      const hit = checks.find(item => item.ok);
      if (hit) {
        return hit.candidate;
      }
    }

    return null;
  };

  useEffect(() => {
    let cancelled = false;
    getOverlayStatus()
      .then(status => {
        if (cancelled) {
          return;
        }
        setOverlayRunning(status.serviceRunning);
        setOverlayMessage(
          status.available
            ? status.canDrawOverlays
              ? 'Android overlay permission granted.'
              : 'Overlay permission still required on this device.'
            : 'Native Android overlay module unavailable in this runtime.',
        );
      })
      .catch(reason => {
        if (!cancelled) {
          setOverlayMessage(String(reason));
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!savedBridgeHydrated || startupDiscoveryComplete || normalizedBaseUrl) {
      return;
    }

    let cancelled = false;

    const discoverDesktopOnLaunch = async () => {
      try {
        const discoveredUrl = await resolveReachableDesktop('');
        if (!discoveredUrl || cancelled) {
          return;
        }

        setBaseUrl(discoveredUrl);
        setBridgeUrlInput(discoveredUrl);
        setDesktopReachable(true);
        await persistPreferredConnection(discoveredUrl, normalizedSessionId);
        if (!normalizedSessionId) {
          setOverlayMessage('Desktop found automatically. Tap Auto Fix All to finish setup.');
        }
      } catch {
        if (!cancelled && !normalizedSessionId) {
          setOverlayMessage('Tap Auto Fix All to find your desktop automatically.');
        }
      } finally {
        if (!cancelled) {
          setStartupDiscoveryComplete(true);
        }
      }
    };

    void discoverDesktopOnLaunch();

    return () => {
      cancelled = true;
    };
  }, [normalizedBaseUrl, normalizedSessionId, persistPreferredConnection, savedBridgeHydrated, startupDiscoveryComplete]);

  useEffect(() => {
    let cancelled = false;

    const hydrateSavedConnection = async () => {
      try {
        const savedFromStorage = await loadSavedBridgeSettings();
        if (cancelled) {
          return;
        }

        const savedUrl = savedFromStorage.baseUrl;
        const savedSession = savedFromStorage.sessionId;

        if (savedUrl) {
          setBaseUrl(savedUrl);
          setBridgeUrlInput(savedUrl);
          if (savedSession) {
            setSessionId(savedSession);
            setOverlayMessage('Loaded saved desktop IP from device storage.');
          } else {
            setOverlayMessage('Loaded saved desktop IP. Tap Fetch Sessions to continue.');
          }
        } else {
          setOverlayMessage('No saved desktop IP found. Enter Desktop IP Address or scan the local network.');
        }
      } catch {
        if (!cancelled) {
          setOverlayMessage('Unable to load saved desktop IP from AsyncStorage.');
        }
      } finally {
        if (!cancelled) {
          setSavedBridgeHydrated(true);
        }
      }
    };

    void hydrateSavedConnection();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const applyDeepLink = async (incomingUrl: string) => {
      const parsed = parseDeepLinkConnection(incomingUrl);
      if (!parsed) {
        return;
      }

      if (parsed.baseUrl) {
        setBaseUrl(parsed.baseUrl);
        setBridgeUrlInput(parsed.baseUrl);
      }
      if (parsed.sessionId) {
        setSessionId(parsed.sessionId);
      }

      if (parsed.baseUrl || parsed.sessionId) {
        await persistPreferredConnection(parsed.baseUrl, parsed.sessionId);
      }

      if (parsed.pairingCode) {
        setPairingCode(parsed.pairingCode);
        setOverlayMessage('Pairing code received from QR. Connecting to desktop...');
        await linkDeviceWithCode(parsed.pairingCode, parsed.baseUrl || normalizedBaseUrl);
        return;
      }

      setOverlayMessage('Desktop URL received from QR link. Connection details applied automatically.');
    };

    const subscription = Linking.addEventListener('url', event => {
      void applyDeepLink(event.url);
    });

    void Linking.getInitialURL().then(initialUrl => {
      if (initialUrl) {
        void applyDeepLink(initialUrl);
      }
    });

    return () => {
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const checkDesktop = async () => {
      if (!normalizedBaseUrl || usingLocalhostBridge) {
        if (!cancelled) {
          setDesktopReachable(null);
        }
        return;
      }

      try {
        const healthy = await fetchLiveBridgeHealth(normalizedBaseUrl);
        if (!cancelled) {
          setDesktopReachable(healthy);
        }
      } catch {
        if (!cancelled) {
          setDesktopReachable(false);
        }
      }
    };

    void checkDesktop();
    const reconnectTimer = setInterval(() => {
      void checkDesktop();
    }, 15000);

    return () => {
      cancelled = true;
      clearInterval(reconnectTimer);
    };
  }, [normalizedBaseUrl, usingLocalhostBridge]);

  const handleStartOverlay = async () => {
    if (!normalizedBaseUrl) {
      setOverlayMessage('Enter your desktop live bridge URL first (for example http://192.168.1.10:8765).');
      return;
    }
    if (usingLocalhostBridge) {
      setOverlayMessage('127.0.0.1 points to your phone itself. Use your desktop/LAN IP in Live bridge URL.');
      return;
    }
    if (!normalizedSessionId) {
      setOverlayMessage('Enter a session ID before starting the overlay.');
      return;
    }
    await persistPreferredConnection(normalizedBaseUrl, normalizedSessionId);
    const message = await startBubbleOverlay(normalizedBaseUrl, normalizedSessionId);
    setOverlayRunning(true);
    setOverlayMessage(message);
  };

  const handleStopOverlay = async () => {
    const message = await stopBubbleOverlay();
    setOverlayRunning(false);
    setOverlayMessage(message);
  };

  const handleFetchSessions = async () => {
    if (!normalizedBaseUrl) {
      setOverlayMessage('Tap Auto Fix All or Find Desktop first. The app will fill the desktop URL for you.');
      return;
    }
    if (usingLocalhostBridge) {
      setOverlayMessage('127.0.0.1 points to your phone itself. Use your desktop/LAN IP in Live bridge URL.');
      return;
    }

    setSessionsLoading(true);
    try {
      const healthy = await fetchLiveBridgeHealth(normalizedBaseUrl);
      if (!healthy) {
        setDesktopReachable(false);
        setOverlayMessage('Desktop bridge is not ready yet. Open Career Copilot on your PC and wait a few seconds.');
        return;
      }

      setDesktopReachable(true);

      const payload = await fetchLiveBridgeSessions(normalizedBaseUrl);
      setAvailableSessions(payload.sessions);
      if (payload.latest_session_id) {
        setSessionId(payload.latest_session_id);
        await persistPreferredConnection(normalizedBaseUrl, payload.latest_session_id);
        setOverlayMessage('Latest desktop session loaded automatically.');
      } else {
        await persistPreferredConnection(normalizedBaseUrl, normalizedSessionId);
        setOverlayMessage(
          'No live session yet. On desktop complete setup and tap Create Session, then Fetch Sessions.',
        );
      }
    } catch (reason) {
      setDesktopReachable(false);
      setOverlayMessage(
        `Could not reach the desktop. ${String(reason)} Keep both devices on the same Wi‑Fi and retry.`,
      );
    } finally {
      setSessionsLoading(false);
    }
  };

  const handleUseLatestSession = () => {
    if (!availableSessions.length) {
      setOverlayMessage('No sessions cached. Tap Fetch Sessions first.');
      return;
    }
    setSessionId(availableSessions[0].session_id);
    setOverlayMessage('Using latest saved desktop session.');
  };

  const handleSaveAndConnect = async () => {
    const normalizedUrl = normalizeBaseUrl(bridgeUrlInput);
    if (!normalizedUrl) {
      setOverlayMessage('Enter Desktop IP Address first, for example http://192.168.1.10:8765.');
      return;
    }
    if (isLocalhostBridgeUrl(normalizedUrl)) {
      setOverlayMessage('This phone cannot use localhost for the desktop bridge. Enter your desktop LAN IP instead.');
      return;
    }

    setSaveConnectLoading(true);
    try {
      setBaseUrl(normalizedUrl);
      setBridgeUrlInput(normalizedUrl);
      await persistPreferredConnection(normalizedUrl, normalizedSessionId);

      const healthy = await fetchLiveBridgeHealth(normalizedUrl);
      setDesktopReachable(healthy);
      if (healthy) {
        setOverlayMessage(`Saved and connected to desktop at ${normalizedUrl}.`);
      } else {
        setOverlayMessage(`Desktop saved as ${normalizedUrl}, but health check is not OK yet.`);
      }
    } catch (reason) {
      setDesktopReachable(false);
      setOverlayMessage(`Saved desktop IP but connect failed: ${String(reason)}`);
    } finally {
      setSaveConnectLoading(false);
    }
  };

  const handleBootstrapSession = async () => {
    if (!normalizedBaseUrl) {
      setOverlayMessage('Enter desktop bridge URL first, then tap Create Session.');
      return;
    }
    if (usingLocalhostBridge) {
      setOverlayMessage('127.0.0.1 points to phone itself. Use desktop LAN IP.');
      return;
    }

    setBootstrapLoading(true);
    try {
      const healthy = await fetchLiveBridgeHealth(normalizedBaseUrl);
      if (!healthy) {
        setDesktopReachable(false);
        setOverlayMessage('Desktop bridge is not reachable. Start desktop helper script first.');
        return;
      }

      setDesktopReachable(true);
      const payload = await bootstrapLiveSession(normalizedBaseUrl);
      setSessionId(payload.session_id);
      await persistPreferredConnection(normalizedBaseUrl, payload.session_id);
      setOverlayMessage(
        payload.created_session
          ? 'New desktop session created and ready.'
          : 'Latest desktop session loaded and worker ensured.',
      );
      const sessionsPayload = await fetchLiveBridgeSessions(normalizedBaseUrl);
      setAvailableSessions(sessionsPayload.sessions);
    } catch (reason) {
      setDesktopReachable(false);
      setOverlayMessage(String(reason));
    } finally {
      setBootstrapLoading(false);
    }
  };

  const handleAutoFixAll = async () => {
    setAutoFixLoading(true);
    try {
      const reachableDesktopUrl = await resolveReachableDesktop(usingLocalhostBridge ? '' : normalizedBaseUrl);
      if (!reachableDesktopUrl) {
        setDesktopReachable(false);
        setOverlayMessage('Desktop not found. Open Career Copilot on your PC, same Wi‑Fi as your phone, then tap Auto Fix All.');
        return;
      }

      setBaseUrl(reachableDesktopUrl);
      setBridgeUrlInput(reachableDesktopUrl);
      setDesktopReachable(true);

      const bootstrap = await bootstrapLiveSession(reachableDesktopUrl);
      const sessionsPayload = await fetchLiveBridgeSessions(reachableDesktopUrl);
      setAvailableSessions(sessionsPayload.sessions);

      const selectedSessionId = sessionsPayload.latest_session_id || bootstrap.session_id;
      if (!selectedSessionId) {
        setOverlayMessage('Auto Fix could not resolve a session ID.');
        return;
      }

      setSessionId(selectedSessionId);
      await persistPreferredConnection(reachableDesktopUrl, selectedSessionId);
      await refresh(selectedSessionId);
      setOverlayMessage('Auto Fix complete: desktop found, session selected, and live data synced.');
    } catch (reason) {
      setDesktopReachable(false);
      setOverlayMessage(`Auto Fix failed: ${String(reason)}`);
    } finally {
      setAutoFixLoading(false);
    }
  };

  const handleFindDesktop = async () => {
    setFindDesktopLoading(true);
    try {
      const hit = await resolveReachableDesktop(usingLocalhostBridge ? '' : normalizedBaseUrl);
      if (hit) {
        setBaseUrl(hit);
        setBridgeUrlInput(hit);
        setDesktopReachable(true);
        await persistPreferredConnection(hit, normalizedSessionId);
        setOverlayMessage(`Desktop auto-discovered at ${hit}.`);
        return;
      }

      setDesktopReachable(false);
      setOverlayMessage('Desktop auto-discovery could not find an active bridge. Run scripts/start_mobile_bridge_quick.ps1 on desktop.');
    } catch (reason) {
      setDesktopReachable(false);
      setOverlayMessage(`Desktop auto-discovery failed: ${String(reason)}`);
    } finally {
      setFindDesktopLoading(false);
    }
  };

  const linkDeviceWithCode = async (rawCode: string, preferredBaseUrl?: string) => {
    const normalizedCode = rawCode.replace(/\D+/g, '').slice(0, 6);
    if (normalizedCode.length !== 6) {
      setOverlayMessage('Enter the 6-digit Link Device code shown on desktop.');
      return;
    }

    setOverlayMessage('Connecting to desktop. Keep this screen open for a moment.');
    setLinkDeviceLoading(true);
    try {
      const startingUrl = normalizeBaseUrl(preferredBaseUrl || (usingLocalhostBridge ? '' : normalizedBaseUrl));
      if (startingUrl) {
        try {
          const payload = await confirmLiveBridgePairingCode(startingUrl, normalizedCode);
          setBaseUrl(startingUrl);
          setBridgeUrlInput(startingUrl);
          setSessionId(payload.session_id);
          setDesktopReachable(true);
          await persistPreferredConnection(startingUrl, payload.session_id);
          await refresh(payload.session_id);
          setPairingCode('');
          setScannerVisible(false);
          setOverlayMessage('Device linked successfully. Desktop and session are now connected.');
          return;
        } catch {
          // Fall back to health-based discovery when the QR-provided bridge URL is stale or unreachable.
        }
      }

      const reachableDesktopUrl = await resolveReachableDesktop(startingUrl);
      if (!reachableDesktopUrl) {
        setDesktopReachable(false);
        setOverlayMessage('Desktop not found. Keep phone and desktop on same Wi-Fi, then retry Link Device.');
        return;
      }

      const payload = await confirmLiveBridgePairingCode(reachableDesktopUrl, normalizedCode);
      setBaseUrl(reachableDesktopUrl);
      setBridgeUrlInput(reachableDesktopUrl);
      setSessionId(payload.session_id);
      setDesktopReachable(true);
      await persistPreferredConnection(reachableDesktopUrl, payload.session_id);
      await refresh(payload.session_id);
      setPairingCode('');
      setScannerVisible(false);
      setOverlayMessage('Device linked successfully. Desktop and session are now connected.');
    } catch (reason) {
      setDesktopReachable(true);
      setOverlayMessage(`Link Device failed: ${String(reason)}`);
    } finally {
      setLinkDeviceLoading(false);
    }
  };

  const handleLinkDevice = async () => {
    await linkDeviceWithCode(pairingCode);
  };

  const handleOpenQrScanner = () => {
    setScannerVisible(current => !current);
  };

  const handleQrRead = async (raw: string) => {
    const value = String(raw || '').trim();
    if (!value) {
      return;
    }

    const now = Date.now();
    if (now - scannerLastReadAt < 1500) {
      return;
    }
    setScannerLastReadAt(now);

    const deep = parseDeepLinkConnection(value);
    if (deep?.pairingCode) {
      if (deep.baseUrl) {
        setBaseUrl(deep.baseUrl);
        setBridgeUrlInput(deep.baseUrl);
      }
      setPairingCode(deep.pairingCode);
      setScannerVisible(false);
      setOverlayMessage('QR scanned. Pairing code detected. Connecting to desktop...');
      await linkDeviceWithCode(deep.pairingCode, deep.baseUrl || normalizedBaseUrl);
      return;
    }

    const scannedCode = extractScannedPairingCode(value);
    if (scannedCode) {
      setPairingCode(scannedCode);
      setScannerVisible(false);
      setOverlayMessage('Scanner returned only digits. Verify the 6-digit code against desktop, then tap Link Device.');
      return;
    }

    setOverlayMessage('QR scanned but code not recognized. Try desktop Link Device QR again.');
  };

  const latestSession = availableSessions.length > 0 ? availableSessions[0] : null;
  const sessionAvailable = availableSessions.length > 0 || normalizedSessionId.length > 0;
  const workerRunning =
    (data?.snapshot.worker_status || '').toLowerCase() === 'running' ||
    (latestSession?.worker_status || '').toLowerCase() === 'running';
  const pairingCodeReady = pairingCode.replace(/\D+/g, '').length === 6;
  const desktopStatusLabel = desktopReachable === true
    ? 'Desktop online'
    : desktopReachable === false
      ? 'Desktop offline'
      : 'Desktop pending';
  const sessionStatusLabel = sessionAvailable ? 'Session ready' : 'Session will attach';
  const workerStatusLabel = workerRunning ? 'Worker live' : 'Worker idle';
  const pairingStateLabel = linkDeviceLoading
    ? 'Connecting...'
    : desktopReachable === true && sessionAvailable
      ? 'Connected'
      : pairingCodeReady
        ? 'Ready to link'
        : 'Waiting for code';

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" />
      <ScrollView contentContainerStyle={styles.container}>
        <StatusHeader />

        <View style={[styles.panel, styles.pairingPanel]}>
          <View style={styles.panelHeroRow}>
            <View style={styles.panelHeroCopy}>
              <Text style={styles.sectionEyebrow}>Desktop pairing</Text>
              <Text style={styles.sectionTitle}>Link Device</Text>
              <Text style={styles.heroText}>
                Scan the desktop QR or type the 6-digit code. This phone will attach to your latest session automatically.
              </Text>
            </View>
            <View style={styles.stateBadge}>
              <Text style={styles.stateBadgeText}>{pairingStateLabel}</Text>
            </View>
          </View>

          <View style={styles.statusChipRow}>
            <View style={[styles.statusChip, desktopReachable === true ? styles.statusChipOk : desktopReachable === false ? styles.statusChipBad : styles.statusChipNeutral]}>
              <Text style={styles.statusChipText}>{desktopStatusLabel}</Text>
            </View>
            <View style={[styles.statusChip, sessionAvailable ? styles.statusChipOk : styles.statusChipNeutral]}>
              <Text style={styles.statusChipText}>{sessionStatusLabel}</Text>
            </View>
            <View style={[styles.statusChip, workerRunning ? styles.statusChipOk : styles.statusChipNeutral]}>
              <Text style={styles.statusChipText}>{workerStatusLabel}</Text>
            </View>
          </View>

          {linkDeviceLoading ? (
            <View style={styles.connectingBanner}>
              <ActivityIndicator color="#f3b53f" size="small" />
              <View style={styles.connectingBannerCopy}>
                <Text style={styles.connectingBannerTitle}>Connecting to desktop</Text>
                <Text style={styles.connectingBannerText}>QR scan received. The app is confirming your pairing code now.</Text>
              </View>
            </View>
          ) : null}

          <View style={styles.inlineActions}>
            <Pressable onPress={() => void handleOpenQrScanner()} style={[styles.secondaryButton, styles.scanButton]}>
              <Text style={styles.secondaryButtonText}>{scannerVisible ? 'Hide Scanner' : 'Scan QR'}</Text>
            </Pressable>
            <Pressable
              disabled={!pairingCodeReady || linkDeviceLoading}
              onPress={() => void handleLinkDevice()}
              style={[styles.primaryButton, styles.linkDeviceButton, (!pairingCodeReady || linkDeviceLoading) && styles.primaryButtonDisabled]}>
              <Text style={styles.primaryButtonText}>{linkDeviceLoading ? 'Linking...' : 'Link Device'}</Text>
            </Pressable>
          </View>

          {scannerVisible ? (
            <View style={styles.scannerWrap}>
              <Camera
                style={styles.scannerCamera}
                cameraType={CameraType.Back}
                scanBarcode
                showFrame
                onReadCode={(event: {nativeEvent: {codeStringValue: string}}) => {
                  void handleQrRead(event.nativeEvent.codeStringValue);
                }}
              />
            </View>
          ) : null}

          <Text style={styles.label}>6-digit code</Text>
          <TextInput
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="number-pad"
            maxLength={6}
            onChangeText={value => setPairingCode(value.replace(/\D+/g, '').slice(0, 6))}
            placeholder="6-digit code"
            placeholderTextColor="#687078"
            style={[styles.input, styles.codeInput, styles.linkDeviceInput]}
            value={pairingCode}
          />
          <Text style={styles.hintText}>
            On desktop Control Room, tap Link Device to generate the QR and code.
          </Text>

          <Text style={styles.label}>Desktop IP Address</Text>
          <View style={styles.desktopIpRow}>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              onChangeText={value => setBridgeUrlInput(value)}
              placeholder="http://192.168.1.10:8765"
              placeholderTextColor="#687078"
              style={[styles.input, styles.desktopIpInput]}
              value={bridgeUrlInput}
            />
            <Pressable
              disabled={saveConnectLoading}
              onPress={() => void handleSaveAndConnect()}
              style={[styles.primaryButton, styles.saveConnectButton, saveConnectLoading && styles.primaryButtonDisabled]}>
              <Text style={styles.primaryButtonText}>{saveConnectLoading ? 'Connecting...' : 'Save & Connect'}</Text>
            </Pressable>
          </View>
          <Text style={styles.hintText}>
            This saved URL is the primary connection method and is loaded first from AsyncStorage key BRIDGE_URL.
          </Text>

          <View style={styles.inlineActions}>
            <Pressable onPress={() => void handleFindDesktop()} style={styles.secondaryButton}>
              <Text style={styles.secondaryButtonText}>{findDesktopLoading ? 'Scanning...' : 'Scan Network'}</Text>
            </Pressable>
          </View>

          <Text style={styles.hintText}>
            Example: http://192.168.1.10:8765 (use Bridge status IP from desktop)
          </Text>

          <View style={styles.summaryCard}>
            <Text style={styles.summaryLabel}>Desktop</Text>
            <Text style={styles.summaryValue}>{normalizedBaseUrl || 'Not connected yet'}</Text>
            <Text style={styles.summaryLabel}>Session</Text>
            <Text style={styles.summaryValue}>{normalizedSessionId || 'Will auto-fill after connect'}</Text>
          </View>
        </View>

        <PermissionBanner message={overlayMessage} overlayRunning={overlayRunning} />

        {loading ? <ActivityIndicator color="#f3b53f" size="large" /> : null}
        {error ? <Text style={styles.errorText}>{error}</Text> : null}

        {data ? (
          <>
            <BubbleCard overlay={data.overlay} session={data.snapshot} />
            <SessionActionGrid
              actions={data.overlay.actions}
              onPress={async actionId => {
                const result = await triggerAction(actionId);
                if (actionId === 'listen') {
                  setOverlayMessage(
                    'Listen sent to desktop. PC mic captures the interviewer — keep phone and PC on same Wi-Fi.',
                  );
                } else {
                  setOverlayMessage(`Queued ${result.queued_action}.`);
                }
              }}
            />
            <View style={styles.panel}>
              <Text style={styles.sectionTitle}>Overlay runtime</Text>
              <View style={styles.inlineActions}>
                <Pressable onPress={() => void handleStartOverlay()} style={styles.primaryButton}>
                  <Text style={styles.primaryButtonText}>Start Bubble</Text>
                </Pressable>
                <Pressable onPress={() => void handleStopOverlay()} style={styles.secondaryButton}>
                  <Text style={styles.secondaryButtonText}>Stop Bubble</Text>
                </Pressable>
              </View>
            </View>
          </>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    backgroundColor: '#0d1418',
    flex: 1,
  },
  container: {
    backgroundColor: '#0d1418',
    gap: 16,
    padding: 20,
    paddingBottom: 32,
  },
  panel: {
    backgroundColor: '#132129',
    borderColor: '#22333e',
    borderRadius: 24,
    borderWidth: 1,
    gap: 12,
    padding: 18,
  },
  pairingPanel: {
    backgroundColor: '#11202a',
    borderColor: '#28404f',
    shadowColor: '#000000',
    shadowOpacity: 0.24,
    shadowRadius: 24,
    shadowOffset: {width: 0, height: 16},
    elevation: 8,
  },
  panelHeroRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
  },
  panelHeroCopy: {
    flex: 1,
    gap: 6,
  },
  sectionEyebrow: {
    color: '#f3b53f',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.1,
    textTransform: 'uppercase',
  },
  heroText: {
    color: '#b1c0c8',
    fontSize: 14,
    lineHeight: 20,
  },
  stateBadge: {
    backgroundColor: 'rgba(243, 181, 63, 0.12)',
    borderColor: 'rgba(243, 181, 63, 0.28)',
    borderRadius: 999,
    borderWidth: 1,
    minHeight: 34,
    paddingHorizontal: 12,
    justifyContent: 'center',
  },
  stateBadgeText: {
    color: '#ffd27a',
    fontSize: 12,
    fontWeight: '700',
  },
  statusChipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  statusChip: {
    borderRadius: 999,
    borderWidth: 1,
    minHeight: 32,
    paddingHorizontal: 12,
    justifyContent: 'center',
  },
  statusChipOk: {
    backgroundColor: 'rgba(126, 216, 165, 0.12)',
    borderColor: 'rgba(126, 216, 165, 0.24)',
  },
  statusChipBad: {
    backgroundColor: 'rgba(255, 142, 114, 0.12)',
    borderColor: 'rgba(255, 142, 114, 0.24)',
  },
  statusChipNeutral: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderColor: '#22333e',
  },
  statusChipText: {
    color: '#eef4f7',
    fontSize: 12,
    fontWeight: '700',
  },
  connectingBanner: {
    alignItems: 'center',
    backgroundColor: 'rgba(243, 181, 63, 0.08)',
    borderColor: 'rgba(243, 181, 63, 0.2)',
    borderRadius: 18,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  connectingBannerCopy: {
    flex: 1,
    gap: 2,
  },
  connectingBannerTitle: {
    color: '#fff0c6',
    fontSize: 14,
    fontWeight: '700',
  },
  connectingBannerText: {
    color: '#d5c79f',
    fontSize: 12,
    lineHeight: 17,
  },
  label: {
    color: '#c8d4db',
    fontSize: 13,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  input: {
    backgroundColor: '#091015',
    borderColor: '#2a424f',
    borderRadius: 18,
    borderWidth: 1,
    color: '#f3f7fa',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  codeInput: {
    flex: 0,
    textAlign: 'center',
    fontSize: 20,
    fontWeight: '700',
    letterSpacing: 6,
  },
  linkDeviceInput: {
    flex: 1,
    minHeight: 64,
  },
  desktopIpRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  desktopIpInput: {
    flex: 1,
  },
  saveConnectButton: {
    flex: 0,
    minHeight: 52,
    minWidth: 148,
    paddingHorizontal: 12,
  },
  summaryCard: {
    backgroundColor: '#0b1014',
    borderColor: '#22333e',
    borderRadius: 18,
    borderWidth: 1,
    gap: 8,
    padding: 16,
  },
  summaryLabel: {
    color: '#97a9b4',
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  summaryValue: {
    color: '#f3f7fa',
    fontSize: 14,
    fontWeight: '600',
  },
  hintText: {
    color: '#97a9b4',
    fontSize: 12,
    lineHeight: 18,
  },
  warningText: {
    color: '#ffb07f',
    fontSize: 12,
    fontWeight: '700',
    lineHeight: 17,
    marginTop: -2,
  },
  inlineActions: {
    flexDirection: 'row',
    gap: 12,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: '#f3b53f',
    borderRadius: 18,
    flex: 1,
    justifyContent: 'center',
    minHeight: 56,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  primaryButtonDisabled: {
    opacity: 0.55,
  },
  linkDeviceButton: {
    flex: 1,
  },
  primaryButtonText: {
    color: '#1a1304',
    fontWeight: '700',
    includeFontPadding: false,
    lineHeight: 20,
    textAlign: 'center',
    textAlignVertical: 'center',
  },
  secondaryButton: {
    alignItems: 'center',
    backgroundColor: '#1b2a34',
    borderRadius: 18,
    flex: 1,
    justifyContent: 'center',
    minHeight: 56,
    paddingVertical: 12,
  },
  scanButton: {
    borderColor: '#29404d',
    borderWidth: 1,
  },
  secondaryButtonText: {
    color: '#f3f7fa',
    fontWeight: '600',
  },
  scannerWrap: {
    borderColor: '#22333e',
    borderRadius: 18,
    borderWidth: 1,
    overflow: 'hidden',
  },
  scannerCamera: {
    height: 240,
    width: '100%',
  },
  sectionTitle: {
    color: '#f3f7fa',
    fontSize: 24,
    fontWeight: '700',
    letterSpacing: -0.4,
  },
  statusText: {
    fontSize: 14,
    fontWeight: '600',
  },
  statusOk: {
    color: '#7ed8a5',
  },
  statusBad: {
    color: '#ff8e72',
  },
  statusNeutral: {
    color: '#c8d4db',
  },
  errorText: {
    color: '#ff8e72',
    fontSize: 14,
  },
});