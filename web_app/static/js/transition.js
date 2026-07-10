/* transition.js — Career Copilot signature page transition (shatter OUT).
 *
 * This is a multi-page Flask app, not an SPA: navigation always ends in a
 * real page load, so only the OUT half needs a canvas-captured animation.
 * The IN half (3D flip on load) animates the real, already-rendered
 * .page-content element directly -- see base.html -- no capture needed.
 *
 * runOut() must never block navigation: if html2canvas is unavailable, if
 * capture fails, or if anything takes too long, it resolves quickly so the
 * caller can navigate immediately.
 */
window.CC_TRANSITION = (function () {
  const COLS = 8;
  const ROWS = 6;
  const OUT_DUR = 440;
  const PAUSE = 60;
  const SAFETY_TIMEOUT = 900; // hard cap so a stuck capture can never block navigation

  function easeIn(t) {
    return t * t * t;
  }

  async function capture(el) {
    if (typeof html2canvas === 'undefined') return null;
    try {
      return await html2canvas(el, {
        backgroundColor: null,
        scale: 1,
        useCORS: true,
        logging: false,
        removeContainer: true,
      });
    } catch (e) {
      return null;
    }
  }

  function makePieces(W, H) {
    const cw = W / COLS;
    const ch = H / ROWS;
    const pieces = [];
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const cx = c * cw + cw / 2;
        const cy = r * ch + ch / 2;
        const dx = cx - W / 2;
        const dy = cy - H / 2;
        const angle = Math.atan2(dy, dx) + (Math.random() - 0.5) * 0.25;
        const spd = 0.6 + Math.random() * 1.0;
        pieces.push({
          sx: c * cw,
          sy: r * ch,
          sw: cw,
          sh: ch,
          tx: c * cw,
          ty: r * ch,
          angle,
          spd,
          rot0: (Math.random() > 0.5 ? 1 : -1) * (0.2 + Math.random() * 0.45),
        });
      }
    }
    return pieces;
  }

  function drawShatter(ctx, pieces, img, t, W, H) {
    ctx.clearRect(0, 0, W, H);
    pieces.forEach((p) => {
      const fly = Math.max(W, H) * 0.65 * t * p.spd;
      const fx = p.tx + Math.cos(p.angle) * fly * (1 + t * 0.6);
      const fy = p.ty + Math.sin(p.angle) * fly * (1 + t * 0.6);
      const rot = p.rot0 * t;
      const sc = 1 - t * 0.35;
      const alpha = 1 - t * 1.1;
      if (alpha <= 0) return;
      ctx.save();
      ctx.globalAlpha = Math.min(1, alpha);
      ctx.translate(fx + p.sw / 2, fy + p.sh / 2);
      ctx.rotate(rot);
      ctx.scale(sc, sc);
      const gap = 1.5;
      ctx.beginPath();
      ctx.rect(-p.sw / 2 + gap, -p.sh / 2 + gap, p.sw - gap * 2, p.sh - gap * 2);
      ctx.clip();
      if (img) {
        ctx.drawImage(img, p.sx, p.sy, p.sw, p.sh, -p.sw / 2, -p.sh / 2, p.sw, p.sh);
      }
      ctx.restore();
    });
  }

  function fallbackFade(fromEl) {
    return new Promise((resolve) => {
      fromEl.style.transition = 'opacity 150ms ease-out';
      fromEl.style.opacity = '0';
      window.setTimeout(resolve, 150);
    });
  }

  /* Shatters fromEl into scattering pieces, then resolves once the screen
   * has gone dramatically empty -- caller navigates to the next page. */
  async function runOutInner(fromEl, container) {
    // fromEl (.page-content) is a narrower, centered column inside the
    // wider container (.premium-main) -- size AND position the canvas to
    // fromEl's own box, not the container's, or every piece lands offset
    // by the centering gap (visibly overlapping the sidebar).
    const W = fromEl.offsetWidth;
    const H = fromEl.offsetHeight;
    if (!W || !H) return fallbackFade(fromEl);

    const img = await capture(fromEl);
    if (!img) return fallbackFade(fromEl);

    const containerRect = container.getBoundingClientRect();
    const fromRect = fromEl.getBoundingClientRect();
    const left = fromRect.left - containerRect.left;
    const top = fromRect.top - containerRect.top;

    let cv = container.querySelector('.cc-transition-canvas');
    if (!cv) {
      cv = document.createElement('canvas');
      cv.className = 'cc-transition-canvas';
      cv.style.cssText = 'position:absolute;pointer-events:none;z-index:100;';
      container.appendChild(cv);
    }
    cv.width = W;
    cv.height = H;
    cv.style.left = left + 'px';
    cv.style.top = top + 'px';
    cv.style.width = W + 'px';
    cv.style.height = H + 'px';
    cv.style.display = 'block';
    const ctx = cv.getContext('2d');

    // fromEl may still carry the page-entry animation's transition
    // declaration (transform/opacity/filter) from when it flipped in --
    // clear it first so hiding the real content is instant, not a lingering
    // 300ms fade racing visibly against the canvas pieces.
    fromEl.style.transition = 'none';
    fromEl.style.opacity = '0';

    const pieces = makePieces(W, H);

    return new Promise((resolve) => {
      let start = null;
      function step(ts) {
        if (!start) start = ts;
        const raw = Math.min(1, (ts - start) / OUT_DUR);
        drawShatter(ctx, pieces, img, easeIn(raw), W, H);
        if (raw < 1) {
          requestAnimationFrame(step);
        } else {
          ctx.clearRect(0, 0, W, H);
          cv.style.display = 'none';
          window.setTimeout(resolve, PAUSE);
        }
      }
      requestAnimationFrame(step);
    });
  }

  function runOut(fromEl, container) {
    if (!fromEl || !container) return Promise.resolve();
    return Promise.race([
      runOutInner(fromEl, container),
      new Promise((resolve) => window.setTimeout(resolve, SAFETY_TIMEOUT)),
    ]);
  }

  return { runOut };
})();
