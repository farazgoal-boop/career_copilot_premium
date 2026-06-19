import {BootstrapSessionResult, LiveBridgeEnvelope, LiveBridgeSessionsResult, QueuedActionResult} from '../types';

function normalizeBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.trim().replace(/\/+$/, '');
  if (!trimmed) {
    return '';
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `http://${trimmed}`;
}

function buildSessionUrl(baseUrl: string, sessionId: string): string {
  const safeBaseUrl = normalizeBaseUrl(baseUrl);
  const safeSessionId = encodeURIComponent(sessionId.trim());
  return `${safeBaseUrl}/session/${safeSessionId}`;
}

function parseNetworkFailure(reason: unknown): Error {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (/network request failed/i.test(message)) {
    return new Error(
      'Network request failed: mobile app could not reach desktop bridge. Use desktop LAN IP (not 127.0.0.1) and ensure desktop bridge is running on port 8765.',
    );
  }
  return new Error(message);
}

async function buildHttpError(prefix: string, response: Response): Promise<Error> {
  let details = '';
  try {
    const payload = (await response.json()) as {error?: string; hint?: string};
    if (payload?.error) {
      details = payload.error;
    }
    if (payload?.hint) {
      details = details ? `${details} ${payload.hint}` : payload.hint;
    }
  } catch {
    // Ignore parse errors and keep status-only message.
  }

  const statusText = `${prefix}: ${response.status}`;
  return new Error(details ? `${statusText} ${details}` : statusText);
}

export async function fetchLiveBridgeSession(baseUrl: string, sessionId: string): Promise<LiveBridgeEnvelope> {
  try {
    const response = await fetch(buildSessionUrl(baseUrl, sessionId));
    if (!response.ok) {
      throw await buildHttpError('Live bridge request failed', response);
    }
    return (await response.json()) as LiveBridgeEnvelope;
  } catch (reason) {
    throw parseNetworkFailure(reason);
  }
}

export async function postLiveBridgeAction(
  baseUrl: string,
  sessionId: string,
  actionId: string,
): Promise<QueuedActionResult> {
  try {
    const response = await fetch(`${buildSessionUrl(baseUrl, sessionId)}/actions/${actionId}`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw await buildHttpError('Action request failed', response);
    }
    return (await response.json()) as QueuedActionResult;
  } catch (reason) {
    throw parseNetworkFailure(reason);
  }
}

export async function fetchLiveBridgeSessions(baseUrl: string): Promise<LiveBridgeSessionsResult> {
  try {
    const response = await fetch(`${normalizeBaseUrl(baseUrl)}/sessions`);
    if (!response.ok) {
      throw await buildHttpError('Session list request failed', response);
    }
    return (await response.json()) as LiveBridgeSessionsResult;
  } catch (reason) {
    throw parseNetworkFailure(reason);
  }
}

export async function fetchLiveBridgeHealth(baseUrl: string): Promise<boolean> {
  try {
    const response = await fetch(`${normalizeBaseUrl(baseUrl)}/health`);
    if (!response.ok) {
      throw await buildHttpError('Desktop bridge health check failed', response);
    }
    const payload = (await response.json()) as {ok?: boolean};
    return Boolean(payload.ok);
  } catch (reason) {
    throw parseNetworkFailure(reason);
  }
}

export async function bootstrapLiveSession(baseUrl: string): Promise<BootstrapSessionResult> {
  try {
    const response = await fetch(`${normalizeBaseUrl(baseUrl)}/bootstrap-session`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw await buildHttpError('Bootstrap session failed', response);
    }
    return (await response.json()) as BootstrapSessionResult;
  } catch (reason) {
    throw parseNetworkFailure(reason);
  }
}

export async function confirmLiveBridgePairingCode(
  baseUrl: string,
  pairingCode: string,
): Promise<{session_id: string; worker_started: boolean}> {
  try {
    const response = await fetch(`${normalizeBaseUrl(baseUrl)}/pairing/confirm`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        pairing_code: pairingCode,
      }),
    });
    if (!response.ok) {
      throw await buildHttpError('Pairing confirm failed', response);
    }
    return (await response.json()) as {session_id: string; worker_started: boolean};
  } catch (reason) {
    throw parseNetworkFailure(reason);
  }
}