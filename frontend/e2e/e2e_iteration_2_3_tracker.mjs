import { chromium } from 'playwright';
import path from 'path';

const ARTIFACTS_DIR = '/home/krishna/.gemini/antigravity/brain/913ec7f7-c5ad-46ab-9267-acc5887bf6b9';
const BASE_URL = 'http://127.0.0.1:5174';

async function runTrackerAudit() {
  console.log('--- Starting CareerOS 2.9.0 Iteration 2.3 Tracker Audit ---');
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

  // 1. Multi-viewport overflow & visual captures on Applications page
  for (const vp of viewports) {
    console.log(`\nTesting viewport: ${vp.name} (${vp.width}x${vp.height})`);
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);

    // Navigate to Applications tab depending on viewport
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

    // Verify zero horizontal overflow
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      const body = document.body;
      const scrollW = Math.max(doc.scrollWidth, body.scrollWidth);
      const innerW = window.innerWidth;
      return {
        scrollWidth: scrollW,
        innerWidth: innerW,
        hasOverflow: scrollW > innerW + 1,
      };
    });

    console.log(`Viewport ${vp.name} overflow check:`, overflow);
    if (overflow.hasOverflow) {
      console.warn(`WARNING: Horizontal overflow detected in ${vp.name}`);
    } else {
      console.log(`✓ Zero horizontal overflow verified for ${vp.name}`);
    }

    const screenshotPath = path.join(ARTIFACTS_DIR, `iteration_2_3_elevated_tracker_${vp.name}.png`);
    await page.screenshot({ path: screenshotPath });
    console.log(`Captured screenshot: ${screenshotPath}`);

    await context.close();
  }

  // 2. Interactive Verification on Desktop (1440px)
  console.log('\n--- Testing Applications Interactive Features (1440px) ---');
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);

  // Navigate to Applications
  await page.click('aside button:has-text("Applications")');
  await page.waitForTimeout(800);

  // A. Test Table view switch
  console.log('Testing Table view switch...');
  const tableTab = page.locator('div[role="tablist"] button:has-text("Table")').first();
  if (await tableTab.isVisible()) {
    await tableTab.click();
    await page.waitForTimeout(800);
    const tableScreenshot = path.join(ARTIFACTS_DIR, 'iteration_2_3_elevated_tracker_table_view.png');
    await page.screenshot({ path: tableScreenshot });
    console.log(`Captured: ${tableScreenshot}`);
  }

  // B. Switch back to Board view
  console.log('Testing Board view switch...');
  const boardTab = page.locator('div[role="tablist"] button:has-text("Board")').first();
  await boardTab.click();
  await page.waitForTimeout(800);

  // C. Test selecting card to inspect details flyout
  console.log('Testing card selection for detail flyout...');
  const cardBtn = page.locator('article button').first();
  if (await cardBtn.isVisible()) {
    await cardBtn.click();
    await page.waitForTimeout(800);
    const detailScreenshot = path.join(ARTIFACTS_DIR, 'iteration_2_3_elevated_tracker_detail_flyout.png');
    await page.screenshot({ path: detailScreenshot });
    console.log(`Captured: ${detailScreenshot}`);
  }

  // D. Test Follow-ups modal
  console.log('Testing Follow-ups modal...');
  const followUpBtn = page.locator('button:has-text("Follow-ups")').first();
  if (await followUpBtn.isVisible()) {
    await followUpBtn.click();
    await page.waitForTimeout(800);
    const closeBtn = page.locator('button[aria-label="Close dialog"]').first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await page.waitForTimeout(400);
      console.log('Follow-ups modal verified and closed.');
    }
  }

  // E. Test Funnel analytics modal
  console.log('Testing Funnel analytics modal...');
  const analyticsBtn = page.locator('button:has-text("Funnel analytics")').first();
  if (await analyticsBtn.isVisible()) {
    await analyticsBtn.click();
    await page.waitForTimeout(800);
    const closeBtn = page.locator('button[aria-label="Close dialog"]').first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await page.waitForTimeout(400);
      console.log('Funnel analytics modal verified and closed.');
    }
  }

  // F. Candidate switching verification
  console.log('Testing Candidate switching on Applications page...');
  const candidateSwitcherBtn = page.locator('header button[title*="Candidate profile context"]');
  await candidateSwitcherBtn.click();
  await page.waitForTimeout(400);

  const candidateBItem = page.locator('button[role="menuitem"]:has-text("Candidate B")');
  if (await candidateBItem.isVisible()) {
    await candidateBItem.click();
    await page.waitForTimeout(1000);
    console.log('Switched to Candidate B on Applications.');

    // Switch back to Candidate 1 (CandidateOne)
    await candidateSwitcherBtn.click();
    await page.waitForTimeout(400);
    const candidateAItem = page.locator('button[role="menuitem"]:has-text("CandidateOne")');
    await candidateAItem.click();
    await page.waitForTimeout(1000);
    console.log('Switched back to Candidate 1 (CandidateOne).');
  }

  await context.close();
  await browser.close();

  console.log('\n--- CareerOS 2.9.0 Iteration 2.3 Tracker Audit Complete ---');
}

runTrackerAudit().catch(err => {
  console.error('Tracker audit failed with error:', err);
  process.exit(1);
});
