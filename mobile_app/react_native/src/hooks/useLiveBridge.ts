import {useEffect, useRef, useState} from 'react';

import {fetchLiveBridgeSession, postLiveBridgeAction} from '../api/liveBridge';
import {LiveBridgeEnvelope, QueuedActionResult} from '../types';

type UseLiveBridgeArgs = {
  baseUrl: string;
  sessionId: string;
  enabled: boolean;
};

type UseLiveBridgeState = {
  data: LiveBridgeEnvelope | null;
  error: string;
  loading: boolean;
  refresh: (targetSessionId?: string) => Promise<void>;
  triggerAction: (actionId: string) => Promise<QueuedActionResult>;
};

export function useLiveBridge({baseUrl, sessionId, enabled}: UseLiveBridgeArgs): UseLiveBridgeState {
  const [data, setData] = useState<LiveBridgeEnvelope | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const initialLoadDone = useRef(false);

  const refresh = async (targetSessionId?: string, options?: {silent?: boolean}) => {
    const resolvedSessionId = (targetSessionId ?? sessionId).trim();
    if (!enabled && !resolvedSessionId) {
      setData(null);
      return;
    }
    const showSpinner = !options?.silent && !initialLoadDone.current;
    if (showSpinner) {
      setLoading(true);
    }
    try {
      const next = await fetchLiveBridgeSession(baseUrl, resolvedSessionId);
      setData(next);
      setError('');
      initialLoadDone.current = true;
    } catch (reason) {
      setError(String(reason));
    } finally {
      if (showSpinner) {
        setLoading(false);
      }
    }
  };

  const triggerAction = async (actionId: string) => {
    const result = await postLiveBridgeAction(baseUrl, sessionId, actionId);
    setData(result);
    return result;
  };

  useEffect(() => {
    if (!enabled) {
      return;
    }
    void refresh();
    const timer = setInterval(() => {
      void refresh(undefined, {silent: true});
    }, 4000);
    return () => {
      clearInterval(timer);
    };
  }, [baseUrl, enabled, sessionId]);

  return {data, error, loading, refresh, triggerAction};
}