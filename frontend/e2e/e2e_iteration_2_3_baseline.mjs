import { chromium } from 'playwright';
import path from 'path';

const ARTIFACTS_DIR = process.env.CAREEROS_E2E_ARTIFACTS || path.join(process.cwd(), 'artifacts');
const BASE_URL = 'http://127.0.0.1:5174';

async function runTrackerBaseline() {
  console.log('--- Capturing CareerOS 2.9.0 Iteration 2.3 Tracker Baselines ---');
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const viewports = [
    { name: '1440px', width: 1440, height: 900 },
    { name: '1280px', width: 1280, height: 800 },
    { name: '768px', width: 768, height: 1024 },
    { name: '390px', width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await context.newPage();
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);

    if (vp.width < 768) {
      const hamburger = page.locator('button[aria-label="Open navigation menu"]').first();
      await hamburger.click();
      await page.waitForTimeout(400);
      const mobileTracker = page.locator('div[role="dialog"][aria-label="Navigation menu"] button:has-text("Applications")').first();
      await mobileTracker.click();
    } else {
      const trackerBtn = page.locator('aside button:has-text("Applications")').first();
      await trackerBtn.click();
    }
    await page.waitForTimeout(1000);

    const screenshotPath = path.join(ARTIFACTS_DIR, `iteration_2_3_baseline_tracker_${vp.name}.png`);
    await page.screenshot({ path: screenshotPath });
    console.log(`Captured: ${screenshotPath}`);
    await context.close();
  }

  // Interactive captures on 1440px
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  await page.click('aside button:has-text("Applications")');
  await page.waitForTimeout(1000);

  // Table view switch
  const tableTab = page.locator('div[role="tablist"] button:has-text("Table")').first();
  if (await tableTab.isVisible()) {
    await tableTab.click();
    await page.waitForTimeout(800);
    const tableScreenshot = path.join(ARTIFACTS_DIR, 'iteration_2_3_baseline_tracker_table_view.png');
    await page.screenshot({ path: tableScreenshot });
    console.log(`Captured: ${tableScreenshot}`);
  }

  // Follow-ups modal
  const followUpBtn = page.locator('button:has-text("Follow-ups")').first();
  if (await followUpBtn.isVisible()) {
    await followUpBtn.click();
    await page.waitForTimeout(800);
    const followUpScreenshot = path.join(ARTIFACTS_DIR, 'iteration_2_3_baseline_tracker_followups_modal.png');
    await page.screenshot({ path: followUpScreenshot });
    console.log(`Captured: ${followUpScreenshot}`);

    // close dialog
    const closeBtn = page.locator('button[aria-label="Close dialog"]').first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await page.waitForTimeout(500);
    }
  }

  // Funnel analytics modal
  const analyticsBtn = page.locator('button:has-text("Funnel analytics")').first();
  if (await analyticsBtn.isVisible()) {
    await analyticsBtn.click();
    await page.waitForTimeout(800);
    const analyticsScreenshot = path.join(ARTIFACTS_DIR, 'iteration_2_3_baseline_tracker_analytics_modal.png');
    await page.screenshot({ path: analyticsScreenshot });
    console.log(`Captured: ${analyticsScreenshot}`);

    const closeBtn = page.locator('button[aria-label="Close dialog"]').first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await page.waitForTimeout(500);
    }
  }

  await context.close();
  await browser.close();
  console.log('--- Baseline capture complete ---');
}

runTrackerBaseline().catch(err => {
  console.error('Error capturing baselines:', err);
  process.exit(1);
});
