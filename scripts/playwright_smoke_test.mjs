import { chromium } from 'playwright';

const baseUrl = process.env.CAREER_COPILOT_BASE_URL || 'http://127.0.0.1:5000';

async function expectText(locator, expected) {
  const text = (await locator.textContent()) || '';
  if (!text.includes(expected)) {
    throw new Error(`Expected text to include "${expected}", got "${text}"`);
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await expectText(page.locator('#command-deck h1').first(), 'Interview Workspace');
    await expectText(page.locator('#live-dock h2').first(), 'Connect a live interview workspace');

    const generatedBefore = await page.locator('#session-id').inputValue();
    await page.locator('#generate-session-button').click();
    const generatedAfter = await page.locator('#session-id').inputValue();
    if (!generatedAfter || generatedAfter === generatedBefore) {
      throw new Error('Generate New did not populate a session id.');
    }

    const stamp = `${Date.now()}`.slice(-6);

    await page.locator('#brief-full-name').fill(`Playwright Smoke ${stamp}`);
    await page.locator('#brief-current-role').fill('Senior Python Developer');

    await page.locator('#wizard-next-button').click();
    await page.locator('#brief-strongest-skill').fill('Python backend development');
    await page.locator('#brief-project-technologies').fill('Python, FastAPI, PostgreSQL');

    await page.locator('#wizard-next-button').click();
    await page.locator('#brief-target-role').fill('Staff Backend Engineer');
    await page.locator('#brief-company-name').fill(`Acme AI ${stamp}`);
    await page.locator('#brief-answer-style').fill('Simple English, concise, confident-humble');
    await page.locator('#brief-expected-questions').fill('Tell me about yourself\nWhy should we hire you?');

    await page.locator('#wizard-save-button').click();
    await page.waitForFunction(() => {
      const status = document.getElementById('status-line');
      return status && /Briefing saved and session created|Connected to/.test(status.textContent || '');
    }, { timeout: 30000 });

    const sessionId = await page.locator('#session-id').inputValue();
    if (!sessionId || !/playwright-smoke-\d+-acme-ai-\d+-staff-backend-engineer-/.test(sessionId)) {
      throw new Error(`Unexpected session id after save: ${sessionId}`);
    }

    await page.waitForSelector('#snapshot-card:not(.hidden)', { timeout: 30000 });
    await expectText(page.locator('#company-name'), `Acme AI ${stamp}`);
    await expectText(page.locator('#role-title'), 'Staff Backend Engineer');

    const recentButtons = page.locator('.recent-session-button');
    await page.waitForFunction(() => document.querySelectorAll('.recent-session-button').length > 0, { timeout: 15000 });
    const recentCount = await recentButtons.count();
    if (recentCount < 1) {
      throw new Error('Expected at least one recent session button after saving briefing.');
    }

    await recentButtons.first().click();
    await page.waitForFunction(() => {
      const status = document.getElementById('status-line');
      return status && /Connected to/.test(status.textContent || '');
    }, { timeout: 15000 });

    const pairingCreate = await page.evaluate(async () => {
      const response = await fetch('/api/pairing/create', { method: 'POST' });
      return { status: response.status, json: await response.json() };
    });
    if (pairingCreate.status !== 200 || !pairingCreate.json.pairing_code) {
      throw new Error(`Pairing create failed: ${JSON.stringify(pairingCreate)}`);
    }

    const pairingConfirm = await page.evaluate(async (pairingCode) => {
      const response = await fetch('/api/pairing/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pairing_code: pairingCode }),
      });
      return { status: response.status, json: await response.json() };
    }, pairingCreate.json.pairing_code);
    if (pairingConfirm.status !== 200) {
      throw new Error(`Pairing confirm failed: ${JSON.stringify(pairingConfirm)}`);
    }

    for (let index = 0; index < 2; index += 1) {
      const toggleResponse = await page.evaluate(async (activeSessionId) => {
        const response = await fetch(`/api/session/${activeSessionId}/actions/toggle`, { method: 'POST' });
        return { status: response.status, json: await response.json() };
      }, sessionId);
      if (toggleResponse.status !== 202) {
        throw new Error(`Toggle failed: ${JSON.stringify(toggleResponse)}`);
      }
      await page.waitForTimeout(1500);
    }

    let finalSnapshot = null;
    for (let attempt = 0; attempt < 30; attempt += 1) {
      finalSnapshot = await page.evaluate(async (activeSessionId) => {
        const response = await fetch(`/api/session/${activeSessionId}`);
        return { status: response.status, json: await response.json() };
      }, sessionId);
      if (finalSnapshot.status === 200 && finalSnapshot.json.overlay?.status === 'answer_ready' && finalSnapshot.json.overlay?.body) {
        break;
      }
      await page.waitForTimeout(2000);
    }

    if (!finalSnapshot || finalSnapshot.status !== 200 || finalSnapshot.json.overlay?.status !== 'answer_ready') {
      throw new Error(`Reply generation did not reach answer_ready: ${JSON.stringify(finalSnapshot)}`);
    }

    const providerLabel = await page.locator('#provider-status .status-indicator__label').textContent();
    const workspaceLabel = await page.locator('#workspace-mode .status-indicator__label').textContent();

    console.log(JSON.stringify({
      baseUrl,
      sessionId,
      recentCount,
      pairingCode: pairingCreate.json.pairing_code,
      pairingExpiresIn: pairingCreate.json.expires_in_seconds,
      replyStatus: finalSnapshot.json.overlay.status,
      replyBody: finalSnapshot.json.overlay.body,
      answerProvider: finalSnapshot.json.overlay.provider_status,
      providerLabel,
      workspaceLabel,
      passed: true,
    }));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});