(() => {
  'use strict';

  const micButton = document.getElementById('browser-mic-toggle');
  if (!micButton) return;

  const compatMessage = document.getElementById('mic-compat-message');
  const sessionId = window.SESSION_ID || '';

  // Which language the caller/interviewer speaks, from Settings -> Language
  // Settings. Best-effort: if this hasn't resolved yet when the mic starts,
  // recognition falls back to en-US rather than blocking the mic button.
  let listenLanguage = 'en-US';
  fetch('/api/settings/language-prefs', { headers: { Accept: 'application/json' } })
    .then((r) => r.json())
    .then((d) => { if (d && d.ok && d.listen_language) listenLanguage = d.listen_language; })
    .catch(() => {});

  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  const supported = Boolean(SpeechRecognitionImpl);

  const STATE_IDLE = 'idle';
  const STATE_LISTENING = 'listening';
  const STATE_PROCESSING = 'processing';
  const STATE_ERROR = 'error';

  function setState(state, label) {
    micButton.classList.remove('mic-idle', 'mic-listening', 'mic-processing', 'mic-error');
    if (state === STATE_LISTENING) {
      micButton.classList.add('mic-listening');
      micButton.textContent = label || 'Listening...';
    } else if (state === STATE_PROCESSING) {
      micButton.classList.add('mic-processing');
      micButton.textContent = label || 'Processing...';
    } else if (state === STATE_ERROR) {
      micButton.classList.add('mic-error');
      micButton.textContent = label || 'Error';
    } else {
      micButton.classList.add('mic-idle');
      micButton.textContent = label || 'Start Browser Mic';
    }
  }

  // --- Continuous session recording (best-effort; independent of Speech Recognition support) ---
  // One MediaRecorder spans the whole session: it starts on the first mic-toggle click and is
  // paused/resumed alongside the toggle rather than stopped, so the whole call is one file.
  let mediaStream = null;
  let mediaRecorder = null;
  let recordedChunks = [];
  let recordingSupported = typeof MediaRecorder !== 'undefined'
    && typeof MediaRecorder.isTypeSupported === 'function'
    && MediaRecorder.isTypeSupported('audio/webm');

  async function ensureRecording() {
    if (!recordingSupported || !sessionId) return;
    if (mediaRecorder) {
      if (mediaRecorder.state === 'paused') mediaRecorder.resume();
      return;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      recordingSupported = false;
      return;
    }
    try {
      mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm' });
    } catch (error) {
      recordingSupported = false;
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
      return;
    }
    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) recordedChunks.push(event.data);
    };
    mediaRecorder.start(1000);
  }

  function pauseRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.pause();
    }
  }

  function finalizeRecording() {
    if (!mediaRecorder) return Promise.resolve(null);
    return new Promise((resolve) => {
      const finish = () => {
        const blob = new Blob(recordedChunks, { type: 'audio/webm' });
        if (mediaStream) {
          mediaStream.getTracks().forEach((track) => track.stop());
        }
        resolve(blob);
      };
      if (mediaRecorder.state === 'inactive') {
        finish();
        return;
      }
      mediaRecorder.addEventListener('stop', finish, { once: true });
      mediaRecorder.stop();
    });
  }

  // Always available -- even in browsers without Speech Recognition support -- so the
  // End Session flow can mark the session ended (and upload a recording, if one exists).
  window.finalizeAndUploadSessionRecording = async function finalizeAndUploadSessionRecording() {
    if (!sessionId) return { ok: false, error: 'No session ID' };
    try {
      if (typeof window.stopBrowserMicListening === 'function') {
        window.stopBrowserMicListening();
      }
      const blob = await finalizeRecording();
      const formData = new FormData();
      if (blob && blob.size > 0) {
        formData.append('recording', blob, 'session-recording.webm');
      }
      const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}/end`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      return { ok: response.ok, ...data };
    } catch (error) {
      return { ok: false, error: error instanceof Error ? error.message : String(error) };
    }
  };

  if (!supported) {
    micButton.disabled = true;
    micButton.classList.add('mic-idle');
    micButton.textContent = 'Not supported in this browser';
    if (compatMessage) compatMessage.style.display = 'block';
    return;
  }

  let active = false;
  let recognition = null;

  async function postTranscript(transcript) {
    if (active) setState(STATE_PROCESSING);
    try {
      const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}/transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript }),
      });
      if (!response.ok) {
        throw new Error(`Transcript post failed: ${response.status}`);
      }
      if (active) setState(STATE_LISTENING, 'Listening... (click to stop)');
    } catch (error) {
      setState(STATE_ERROR, 'Send failed');
      window.showToast?.('Browser transcript failed to send', 'error');
    }
  }

  function createRecognition() {
    const instance = new SpeechRecognitionImpl();
    instance.continuous = true;
    instance.interimResults = true;
    instance.lang = listenLanguage;

    instance.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) {
          const text = (result[0] && result[0].transcript || '').trim();
          if (text) postTranscript(text);
        }
      }
    };

    instance.onerror = (event) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return;
      setState(STATE_ERROR, `Error: ${event.error}`);
    };

    instance.onend = () => {
      if (active) {
        try {
          instance.start();
        } catch (error) {
          // Already running or a transient restart race — safe to ignore.
        }
      }
    };

    return instance;
  }

  function startListening() {
    if (!sessionId) {
      setState(STATE_ERROR, 'No session ID');
      return;
    }
    recognition = createRecognition();
    try {
      recognition.start();
    } catch (error) {
      setState(STATE_ERROR, 'Could not start');
      return;
    }
    active = true;
    setState(STATE_LISTENING, 'Listening... (click to stop)');
    ensureRecording();
  }

  function stopListening() {
    active = false;
    if (recognition) {
      recognition.onend = null;
      recognition.stop();
      recognition = null;
    }
    pauseRecording();
    setState(STATE_IDLE, 'Start Browser Mic');
  }

  window.stopBrowserMicListening = stopListening;

  micButton.addEventListener('click', () => {
    if (active) {
      stopListening();
    } else {
      startListening();
    }
  });

  setState(STATE_IDLE, 'Start Browser Mic');
})();
