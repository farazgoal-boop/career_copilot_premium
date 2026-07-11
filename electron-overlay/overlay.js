// Renderer logic. No Node integration here (contextIsolation: true,
// nodeIntegration: false) -- only browser APIs (fetch/EventSource/DOM) plus
// window.overlayAPI exposed by preload.js. Mirrors the same Flask endpoints
// premium_launcher.py's PySide6 overlay already uses/could use -- see the
// route line numbers in comments below, all verified against web_app/routes.py.

const BASE_URL = new URLSearchParams(window.location.search).get('base') || 'http://127.0.0.1:5000';

const el = {
  pill: document.getElementById('pill'),
  question: document.getElementById('questionBox'),
  answer: document.getElementById('answerBox'),
  confidence: document.getElementById('confidenceValue'),
  provider: document.getElementById('providerLabel'),
  alternatives: document.getElementById('alternativesBox'),
  listenLang: document.getElementById('listenLang'),
  replyLang: document.getElementById('replyLang'),
  manualInput: document.getElementById('manualInput'),
  apiStatus: document.getElementById('apiStatus'),
  audioStatus: document.getElementById('audioStatus'),
  langStatus: document.getElementById('langStatus'),
  opacitySlider: document.getElementById('opacitySlider'),
  hideBtn: document.getElementById('hideBtn'),
  btnListen: document.getElementById('btnListen'),
  btnCopy: document.getElementById('btnCopy'),
  btnRegen: document.getElementById('btnRegen'),
  btnSimple: document.getElementById('btnSimple'),
  btnSend: document.getElementById('btnSend'),
};

let currentSessionId = '';
let currentEventSource = null;
let currentAlternatives = [];
let lastQuestionText = '';

function setPill(text, mode) {
  el.pill.textContent = text;
  el.pill.className = 'pill' + (mode ? ' ' + mode : '');
}

// Mirrors premium_launcher.py's poll_session_updates()/_apply_session_payload()
// (lines ~373-421), which reads GET /api/sessions/recent (routes.py:493)
// then GET /api/session/<id> (routes.py:1012). We reuse the same "most
// recent session" resolution instead of adding a session-less Flask route.
async function resolveActiveSession() {
  try {
    const response = await fetch(`${BASE_URL}/api/sessions/recent`);
    const data = await response.json();
    const sessions = data.sessions || [];
    if (!sessions.length) return '';
    return String(sessions[0].session_id || '').trim();
  } catch (error) {
    console.warn('[overlay] Could not resolve active session:', error);
    return '';
  }
}

// GET /api/session/<id>/events (routes.py:1397) is Server-Sent Events,
// backed by web_app/websocket.py's stream_session_events(). Push-based --
// strictly better than the 4s poll the PySide6 overlay uses today.
function connectSessionEvents(sessionId) {
  if (currentEventSource) {
    currentEventSource.close();
  }
  currentEventSource = new EventSource(`${BASE_URL}/api/session/${sessionId}/events`);
  currentEventSource.addEventListener('snapshot', (event) => {
    try {
      applySessionPayload(JSON.parse(event.data));
    } catch (error) {
      console.warn('[overlay] Failed to parse session snapshot:', error);
    }
  });
  currentEventSource.onerror = () => {
    // EventSource auto-reconnects; nothing to do here.
  };
}

// Same field shape premium_launcher.py's _apply_session_payload() already
// consumes (overlay.status/body/headline/alternatives/confidence_score/
// provider_status, snapshot.last_transcript/last_answer).
function applySessionPayload(payload) {
  const overlay = payload.overlay || {};
  const snapshot = payload.snapshot || {};
  const status = String(overlay.status || 'idle');
  const answer = overlay.body || overlay.suggested_answer || snapshot.last_answer || '';

  if (status === 'answer_ready') {
    const transcript = overlay.headline || overlay.transcript || snapshot.last_transcript || 'Question captured';
    el.question.textContent = String(transcript);
    el.answer.textContent = String(answer || 'Answer generating...');
    currentAlternatives = overlay.alternatives || [];
    renderAlternatives(currentAlternatives);
    setConfidence(overlay.confidence_score ?? 91);
    el.provider.textContent = `AI ${overlay.provider_status || 'AI'}`;
    setPill('READY');
  } else if (status === 'listening') {
    el.question.textContent = 'Listening for interviewer question...';
    el.answer.textContent = 'Waiting for question...';
    setPill('LISTENING', 'listening');
  }
}

function renderAlternatives(alternatives) {
  if (!alternatives || !alternatives.length) {
    el.alternatives.textContent = 'No alternatives yet.';
    return;
  }
  el.alternatives.textContent = alternatives.map((a) => `- ${a}`).join('\n\n');
}

function setConfidence(score) {
  el.confidence.textContent = `${score}%`;
  el.confidence.style.color = score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--yellow)' : 'var(--red)';
}

// POST /api/session/<id>/listen (routes.py:1132) -- exact HTTP equivalent
// of overlay.py's _run_live_listen_request()/run_live_listen_cycle().
async function triggerListen() {
  if (!currentSessionId) {
    currentSessionId = await resolveActiveSession();
    if (!currentSessionId) {
      el.answer.textContent = 'No active session. Open the dashboard and click Create Session first.';
      setPill('ERROR', 'error');
      return;
    }
    connectSessionEvents(currentSessionId);
  }
  el.question.textContent = 'Listening to interviewer...';
  el.answer.textContent = 'Capturing call audio and generating your script...';
  setPill('LISTENING', 'listening');

  try {
    const response = await fetch(`${BASE_URL}/api/session/${currentSessionId}/listen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        listen_language: el.listenLang.value,
        reply_language: el.replyLang.value,
      }),
    });
    const result = await response.json();
    if (!result.ok) throw new Error(result.error || 'Live listen failed.');
    lastQuestionText = result.transcript || '';
    el.question.textContent = result.transcript || 'No transcript yet.';
    el.answer.textContent = result.suggested_answer || 'No answer yet.';
    currentAlternatives = result.alternatives || [];
    renderAlternatives(currentAlternatives);
    el.provider.textContent = `AI ${result.provider_status || 'AI'}`;
    setConfidence(88);
    setPill('READY');
  } catch (error) {
    el.answer.textContent = `Error: ${error.message}`;
    setPill('ERROR', 'error');
  }
}

// POST /api/session/<id>/transcript (routes.py:1176) -- equivalent of
// overlay.py's _generate_manual_answer()/answer_builder.generate_manual_answer,
// resolved via the same session-lookup used above instead of adding a new
// session-less Flask route.
async function sendManualQuestion(text) {
  if (!text.trim()) return;
  if (!currentSessionId) {
    currentSessionId = await resolveActiveSession();
    if (!currentSessionId) {
      el.answer.textContent = 'No active session. Open the dashboard and click Create Session first.';
      setPill('ERROR', 'error');
      return;
    }
    connectSessionEvents(currentSessionId);
  }
  lastQuestionText = text;
  el.question.textContent = `Q: ${text}`;
  el.answer.textContent = 'Generating answer...';
  setPill('THINKING');

  try {
    const response = await fetch(`${BASE_URL}/api/session/${currentSessionId}/transcript`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript: text }),
    });
    const result = await response.json();
    if (!result.ok) throw new Error(result.error || 'Answer generation failed.');
    el.answer.textContent = result.suggested_answer || 'No answer generated. Please try again.';
    currentAlternatives = result.alternatives || [];
    renderAlternatives(currentAlternatives);
    el.provider.textContent = `AI ${result.provider_status || 'AI'}`;
    setConfidence(88);
    setPill('READY');
  } catch (error) {
    el.answer.textContent = `Error: ${error.message}`;
    setPill('ERROR', 'error');
  }
}

// GET /api/settings/language-prefs (routes.py:604) already returns both the
// saved prefs and the full language_options list -- no new route needed.
async function loadLanguageOptions() {
  try {
    const response = await fetch(`${BASE_URL}/api/settings/language-prefs`);
    const data = await response.json();
    const options = data.language_options || [];
    for (const opt of options) {
      el.listenLang.add(new Option(opt.label, opt.code));
      el.replyLang.add(new Option(opt.label, opt.code));
    }
    el.listenLang.value = data.listen_language || 'en-US';
    el.replyLang.value = data.reply_language || 'en-US';
    updateLangStatusLabel();
  } catch (error) {
    console.warn('[overlay] Could not load language options:', error);
  }
}

function updateLangStatusLabel() {
  const listenLabel = el.listenLang.selectedOptions[0]?.text || el.listenLang.value;
  const replyLabel = el.replyLang.selectedOptions[0]?.text || el.replyLang.value;
  el.langStatus.textContent = `Languages: ${listenLabel} -> ${replyLabel}`;
}

// POST /api/settings/language-prefs (routes.py:619).
async function saveLanguagePrefs() {
  try {
    await fetch(`${BASE_URL}/api/settings/language-prefs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        listen_language: el.listenLang.value,
        reply_language: el.replyLang.value,
      }),
    });
    updateLangStatusLabel();
  } catch (error) {
    console.warn('[overlay] Could not save language prefs:', error);
  }
}

// GET /api/system/preflight (routes.py:316) -- same checks array the
// dashboard's System Status page renders; adapted here into the compact
// status-bar strings overlay.py's own _build_status_labels() shows.
async function refreshStatusBar() {
  try {
    const response = await fetch(`${BASE_URL}/api/system/preflight`);
    const data = await response.json();
    const checks = data.checks || [];
    const mistral = checks.find((c) => c.id === 'mistral');
    const mic = checks.find((c) => c.id === 'microphone');
    el.apiStatus.textContent = mistral ? `API: ${mistral.ok ? 'Mistral Connected' : mistral.hint}` : 'API: Unknown';
    el.apiStatus.style.color = mistral?.ok ? 'var(--green)' : 'var(--red)';
    el.audioStatus.textContent = mic ? `Audio: ${mic.hint}` : 'Audio: Unknown';
    el.audioStatus.style.color = mic?.ok ? 'var(--green)' : 'var(--red)';
  } catch (error) {
    el.apiStatus.textContent = 'API: Status unavailable';
    el.audioStatus.textContent = 'Audio: Status unavailable';
  }
}

function pollForSessionChange() {
  resolveActiveSession().then((sessionId) => {
    if (sessionId && sessionId !== currentSessionId) {
      currentSessionId = sessionId;
      connectSessionEvents(currentSessionId);
    }
  });
}

el.hideBtn.addEventListener('click', () => window.overlayAPI.hide());
el.btnListen.addEventListener('click', triggerListen);
el.btnSend.addEventListener('click', () => {
  const text = el.manualInput.value.trim();
  el.manualInput.value = '';
  sendManualQuestion(text);
});
el.manualInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    const text = el.manualInput.value.trim();
    el.manualInput.value = '';
    sendManualQuestion(text);
  }
});
el.btnCopy.addEventListener('click', () => {
  const text = el.answer.textContent;
  if (text && text !== 'Processing answer...' && text !== 'No answer yet.') {
    window.overlayAPI.copyText(text);
    el.btnCopy.textContent = 'Copied!';
    setTimeout(() => { el.btnCopy.textContent = 'Copy Answer'; }, 2000);
  }
});
el.btnSimple.addEventListener('click', () => {
  if (currentAlternatives.length) {
    el.answer.textContent = currentAlternatives[0];
  }
});
el.btnRegen.addEventListener('click', () => {
  if (lastQuestionText) sendManualQuestion(lastQuestionText);
});
el.listenLang.addEventListener('change', saveLanguagePrefs);
el.replyLang.addEventListener('change', saveLanguagePrefs);
el.opacitySlider.addEventListener('input', () => {
  window.overlayAPI.setOpacity(Number(el.opacitySlider.value) / 100);
});

window.overlayAPI.onHotkeyListen(triggerListen);

(async function init() {
  await loadLanguageOptions();
  currentSessionId = await resolveActiveSession();
  if (currentSessionId) connectSessionEvents(currentSessionId);
  refreshStatusBar();
  setInterval(pollForSessionChange, 4000);
  setInterval(refreshStatusBar, 30000);
})();
