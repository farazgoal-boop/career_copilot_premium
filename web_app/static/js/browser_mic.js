(() => {
  'use strict';

  const micButton = document.getElementById('browser-mic-toggle');
  if (!micButton) return;

  const compatMessage = document.getElementById('mic-compat-message');
  const sessionId = window.SESSION_ID || '';

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
    instance.lang = 'en-US';

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
  }

  function stopListening() {
    active = false;
    if (recognition) {
      recognition.onend = null;
      recognition.stop();
      recognition = null;
    }
    setState(STATE_IDLE, 'Start Browser Mic');
  }

  micButton.addEventListener('click', () => {
    if (active) {
      stopListening();
    } else {
      startListening();
    }
  });

  setState(STATE_IDLE, 'Start Browser Mic');
})();
