/**
 * Career Copilot Premium — client-readiness Playwright suite.
 *
 * Prerequisite: app running (START_PREMIUM.bat or installed EXE) with dashboard at :5000
 *
 * Run:
 *   powershell -File scripts\run_playwright_client_test.ps1
 *   or: RUN_PLAYWRIGHT_TESTS.bat
 */
import { chromium } from 'playwright';

const baseUrl = (process.env.CAREER_COPILOT_BASE_URL || 'http://127.0.0.1:5000').replace(/\/$/, '');

function assertTrue(condition, message) {
  if (!condition) throw new Error(message);
}

function hasTofu(text) {
  if (!text) return false;
  return /[\uFFFD\uFFF0-\uFFFF]/.test(text) || /[\u0000-\u0008\u000e-\u001f]/.test(text);
}

function includesAny(text, words) {
  const hay = (text || '').toLowerCase();
  return words.some((word) => hay.includes(word.toLowerCase()));
}

async function fetchJson(page, path, options = {}) {
  return page.evaluate(async ({ url, init }) => {
    const response = await fetch(url, init);
    let json = null;
    try {
      json = await response.json();
    } catch {
      json = null;
    }
    return { status: response.status, json };
  }, { url: `${baseUrl}${path}`, init: options });
}

async function expectText(locator, expected) {
  const text = (await locator.textContent()) || '';
  if (!text.includes(expected)) {
    throw new Error(`Expected text to include "${expected}", got "${text}"`);
  }
}

async function runBriefingFlow(page, stamp) {
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await expectText(page.locator('#command-deck h1').first(), 'Interview Workspace');

  const generatedBefore = await page.locator('#session-id').inputValue();
  await page.locator('#generate-session-button').click();
  const generatedAfter = await page.locator('#session-id').inputValue();
  assertTrue(generatedAfter && generatedAfter !== generatedBefore, 'Generate New did not populate a session id.');

  await page.locator('#brief-full-name').fill(`Playwright Client ${stamp}`);
  await page.locator('#brief-current-role').fill('Senior Python Developer');
  await page.locator('#wizard-next-button').click();

  await page.locator('#brief-strongest-skill').fill('Python backend development');
  await page.locator('#brief-project-technologies').fill('Python, FastAPI, PostgreSQL');
  await page.locator('#wizard-next-button').click();

  await page.locator('#brief-target-role').fill('Staff Backend Engineer');
  await page.locator('#brief-company-name').fill(`Acme AI ${stamp}`);
  await page.locator('#brief-answer-style').fill('Simple English, concise, confident');
  await page.locator('#brief-expected-questions').fill(
    'What is your experience with Python?\nWhy should we hire you?'
  );
  await page.locator('#wizard-save-button').click();

  await page.waitForFunction(() => {
    const status = document.getElementById('status-line');
    return status && /Briefing saved and session created|Connected to/.test(status.textContent || '');
  }, { timeout: 45000 });

  const sessionId = await page.locator('#session-id').inputValue();
  assertTrue(sessionId, 'Session id missing after briefing save.');

  await page.waitForSelector('#snapshot-card:not(.hidden)', { timeout: 30000 });
  return sessionId;
}

async function main() {
  const results = {
    baseUrl,
    passed: [],
    failed: [],
  };
  const stamp = `${Date.now()}`.slice(-6);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    // 1) Health endpoint (must be 200 without activation)
    const health = await fetchJson(page, '/api/health');
    assertTrue(health.status === 200 && health.json?.status === 'ok', `Health failed: ${JSON.stringify(health)}`);
    results.passed.push('health');

    // 2) Dashboard shell
    const sessionId = await runBriefingFlow(page, stamp);
    results.passed.push('briefing_and_session');

    // 3) Typed transcript answer — question-specific (no mic needed)
    const testQuestion = 'What is your experience with Python backend development?';
    const transcriptResp = await fetchJson(page, `/api/session/${sessionId}/transcript`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transcript: testQuestion }),
    });
    assertTrue(transcriptResp.status === 200 && transcriptResp.json?.ok, `Transcript API failed: ${JSON.stringify(transcriptResp)}`);

    const answer = String(transcriptResp.json.suggested_answer || '');
    const returnedTranscript = String(transcriptResp.json.transcript || '');
    assertTrue(!hasTofu(returnedTranscript), `Transcript has tofu/garbage: ${returnedTranscript}`);
    assertTrue(!hasTofu(answer), `Answer has tofu/garbage: ${answer}`);
    assertTrue(answer.length > 20, `Answer too short: ${answer}`);
    assertTrue(
      includesAny(answer, ['python', 'backend', 'api', 'develop', 'experience', 'fastapi']),
      `Answer not related to Python question. Got: ${answer}`
    );
    results.passed.push('transcript_answer_relevance');

    // 4) Live Dock snapshot — headline readable
    await page.waitForTimeout(1500);
    const snapshot = await fetchJson(page, `/api/session/${sessionId}`);
    assertTrue(snapshot.status === 200, `Snapshot fetch failed: ${JSON.stringify(snapshot)}`);
    const headline = String(snapshot.json?.overlay?.headline || '');
    const body = String(snapshot.json?.overlay?.body || '');
    assertTrue(!hasTofu(headline), `Live Dock headline tofu: ${headline}`);
    assertTrue(!hasTofu(body), `Live Dock body tofu: ${body}`);
    if (headline) {
      assertTrue(
        includesAny(headline, ['python', 'experience', 'backend', 'develop']),
        `Headline not tied to question: ${headline}`
      );
    }
    results.passed.push('live_dock_snapshot');

    // 5) UI Live Dock panel text (browser render)
    await page.locator('[data-section-target="live-dock"]').click({ timeout: 5000 });
    await page.waitForTimeout(800);
    const headlineUi = await page.locator('#headline').textContent();
    const bodyUi = await page.locator('#body').textContent();
    assertTrue(!hasTofu(headlineUi || ''), `UI headline tofu: ${headlineUi}`);
    assertTrue(!hasTofu(bodyUi || ''), `UI body tofu: ${bodyUi}`);
    results.passed.push('live_dock_ui');

    // 6) Recent sessions list
    await page.waitForFunction(() => document.querySelectorAll('.recent-session-button').length > 0, { timeout: 15000 });
    results.passed.push('recent_sessions');

    // 7) Pairing API
    const pairingCreate = await fetchJson(page, '/api/pairing/create', { method: 'POST' });
    assertTrue(pairingCreate.status === 200 && pairingCreate.json?.pairing_code, `Pairing create failed: ${JSON.stringify(pairingCreate)}`);
    results.passed.push('pairing_create');

    console.log(JSON.stringify({
      ok: true,
      baseUrl,
      sessionId,
      testQuestion,
      transcript: returnedTranscript,
      answerPreview: answer.slice(0, 220),
      provider: transcriptResp.json.provider_status,
      headline: headline || headlineUi,
      passed: results.passed,
      stamp,
    }, null, 2));
  } catch (error) {
    console.error(JSON.stringify({
      ok: false,
      baseUrl,
      passed: results.passed,
      error: error?.message || String(error),
    }, null, 2));
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main();
