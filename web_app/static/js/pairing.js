/* Mobile device pairing modal — Career Copilot Premium */
(function () {
  'use strict';

  function renderPairingDigits(element, value, isPlaceholder) {
    if (!element) return;
    var chars = String(value || '').trim().split('');
    if (!chars.length) { element.textContent = ''; return; }
    element.classList.toggle('pairing-digits--placeholder', !!isPlaceholder);
    element.innerHTML = chars.map(function (ch, i) {
      return '<span class="pairing-digit pairing-digit--' + (i % 2 === 0 ? 'cool' : 'warm') + '">' + ch + '</span>';
    }).join('');
  }

  async function openPairingModal() {
    var modal   = document.getElementById('pairing-modal');
    var qrWrap  = document.getElementById('pairing-qr-wrap');
    var digits  = document.getElementById('pairing-digits');
    var expiry  = document.getElementById('pairing-expiry');
    var copyBtn = document.getElementById('pairing-copy-btn');
    var refreshBtn = document.getElementById('pairing-refresh-btn');
    var closeBtn   = document.getElementById('pairing-modal-close');

    if (!modal) return;

    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    if (qrWrap) qrWrap.innerHTML = '<div class="pairing-qr-loading">Generating&hellip;</div>';
    renderPairingDigits(digits, '------', true);
    if (expiry)  expiry.textContent = '';
    if (copyBtn) { copyBtn.disabled = true; copyBtn.textContent = 'Copy code'; }

    function closeModal() {
      modal.classList.add('hidden');
      document.body.style.overflow = '';
    }

    if (closeBtn)  closeBtn.onclick  = closeModal;
    if (refreshBtn) refreshBtn.onclick = function () { openPairingModal(); };
    modal.onclick = function (e) { if (e.target === modal) closeModal(); };

    try {
      var resp = await fetch('/api/pairing/create', { method: 'POST' });
      var payload = await resp.json();
      if (!resp.ok) throw new Error(payload.error || 'Request failed (' + resp.status + ')');

      var code = String(payload.pairing_code || '').trim();
      if (!code) throw new Error('No pairing code returned.');

      renderPairingDigits(digits, code);

      var expiresSec = Number(payload.expires_in_seconds || 180);
      if (expiry) {
        var mins = Math.max(1, Math.round(expiresSec / 60));
        expiry.textContent = 'Expires in ' + mins + ' minute' + (mins !== 1 ? 's' : '');
      }

      if (qrWrap) {
        qrWrap.innerHTML = '<div class="pairing-qr-loading">Rendering QR&hellip;</div>';
        var qrResp = await fetch('/api/pairing/qr/' + encodeURIComponent(code), { cache: 'no-store' });
        if (!qrResp.ok) throw new Error('QR request failed (' + qrResp.status + ')');
        var ct = String(qrResp.headers.get('content-type') || '').toLowerCase();
        qrWrap.innerHTML = '';
        if (ct.includes('image/svg') || ct.includes('text/html')) {
          qrWrap.innerHTML = await qrResp.text();
          var svgEl = qrWrap.querySelector('svg');
          if (svgEl) { svgEl.removeAttribute('width'); svgEl.removeAttribute('height'); svgEl.style.cssText = 'width:100%;height:100%;display:block'; }
        } else {
          var blob = await qrResp.blob();
          var img  = document.createElement('img');
          img.src  = URL.createObjectURL(blob);
          img.alt  = 'QR code for pairing code ' + code;
          img.className = 'pairing-qr-img';
          img.onload = function () { URL.revokeObjectURL(img.src); };
          img.onerror = function () {
            qrWrap.innerHTML = '<div class="pairing-qr-fallback">QR unavailable. Use code <strong>' + code + '</strong>.</div>';
          };
          qrWrap.appendChild(img);
        }
      }

      if (copyBtn) {
        copyBtn.disabled = false;
        copyBtn.onclick = async function () {
          try {
            await navigator.clipboard.writeText(code);
            copyBtn.textContent = '✓ Copied';
            setTimeout(function () { copyBtn.textContent = 'Copy code'; }, 2000);
          } catch {
            copyBtn.textContent = code;
          }
        };
      }
    } catch (err) {
      if (qrWrap) qrWrap.innerHTML = '<div class="pairing-qr-error">' + String(err.message || err) + '</div>';
      renderPairingDigits(digits, 'ERROR', true);
    }
  }

  window.openPairingModal = openPairingModal;
})();
