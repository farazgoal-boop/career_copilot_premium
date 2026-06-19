export type LiveBridgeAction = {
  action_id: string;
  label: string;
  session_command: string;
  fallback_action?: string | null;
  href: string;
  method: 'POST';
};

export type MobileBridgeSnapshot = {
  source_version: string;
  session_id: string;
  profile_name: string;
  company_name: string;
  role_title: string;
  worker_status: string;
  command_queue_path: string;
  session_database_path: string;
  updated_at: string;
  bubble: {
    status: string;
    visible: boolean;
    headline: string;
    body: string;
    confidence_score: number;
    provider_status: string;
    alternatives: string[];
  };
};

export type LiveBridgeEnvelope = {
  snapshot: MobileBridgeSnapshot;
  overlay: {
    mode: 'compact' | 'expanded';
    status: string;
    headline: string;
    body: string;
    confidence_score: number;
    provider_status: string;
    alternatives: string[];
    actions: LiveBridgeAction[];
  };
  transport: {
    protocol: 'http';
    base_url: string;
    session_href: string;
  };
};

export type QueuedActionResult = LiveBridgeEnvelope & {
  queued_action: string;
  queue_path: string;
};

export type SessionSummary = {
  session_id: string;
  profile_name: string;
  company_name: string;
  role_title: string;
  worker_status: string;
  updated_at: string;
  session_href: string;
};

export type LiveBridgeSessionsResult = {
  sessions: SessionSummary[];
  latest_session_id: string;
  count: number;
};

export type BootstrapSessionResult = {
  session_id: string;
  created_session: boolean;
  worker_started: boolean;
};

export type OverlayNativeStatus = {
  available: boolean;
  canDrawOverlays: boolean;
  serviceRunning: boolean;
};