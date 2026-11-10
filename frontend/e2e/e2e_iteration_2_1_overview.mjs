import { chromium } from 'playwright';
import path from 'path';

const ARTIFACTS_DIR = '/home/krishna/.gemini/antigravity/brain/913ec7f7-c5ad-46ab-9267-acc5887bf6b9';
const BASE_URL = 'http://127.0.0.1:5174';

async function runOverviewAudit() {
  console.log('--- Starting CareerOS 2.9.0 Iteration 2.1 Overview Audit ---');
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

  // 1. Multi-viewport overflow & visual captures
  for (const vp of viewports) {
    console.log(`\nTesting viewport: ${vp.name} (${vp.width}x${vp.height})`);
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
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

    const screenshotPath = path.join(ARTIFACTS_DIR, `iteration_2_1_elevated_overview_${vp.name}.png`);
    await page.screenshot({ path: screenshotPath });
    console.log(`Captured screenshot: ${screenshotPath}`);

    await context.close();
  }

  // 2. Interactive Verification on Desktop (1440px)
  console.log('\n--- Testing Overview Interactive Features (1440px) ---');
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);

  // A. Verify KPI drill-down click (Active Applications -> Applications tab)
  console.log('Testing Active Applications KPI card click-through...');
  const activeAppsCard = page.locator('div[role="button"]:has-text("Active applications")').first();
  await activeAppsCard.click();
  await page.waitForTimeout(600);

  // Check header breadcrumb or heading
  const currentHeading = await page.evaluate(() => {
    const h1 = document.querySelector('h1');
    return h1 ? h1.innerText : '';
  });
  console.log('Navigated page heading:', currentHeading);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'iteration_2_1_kpi_interaction_navigated.png') });

  // B. Navigate back to Overview
  await page.click('aside button:has-text("Overview")');
  await page.waitForTimeout(600);

  // C. Test Recent Activity item click
  console.log('Testing Recent Activity item click-through...');
  const activityItem = page.locator('div[role="button"]:has-text("Tailored Resume")').first();
  if (await activityItem.isVisible()) {
    await activityItem.click();
    await page.waitForTimeout(600);
    const resumeHeading = await page.evaluate(() => {
      const h1 = document.querySelector('h1');
      return h1 ? h1.innerText : '';
    });
    console.log('After activity click, heading:', resumeHeading);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'iteration_2_1_activity_stream_navigated.png') });
  }

  // D. Return to Overview and test Candidate Switching
  console.log('Testing candidate profile switcher from Overview...');
  await page.click('aside button:has-text("Overview")');
  await page.waitForTimeout(600);

  const candidateSwitcherBtn = page.locator('header button[title*="Candidate profile context"]');
  await candidateSwitcherBtn.click();
  await page.waitForTimeout(400);

  // Switch to Candidate B
  const candidateBItem = page.locator('button[role="menuitem"]:has-text("Candidate B")');
  if (await candidateBItem.isVisible()) {
    await candidateBItem.click();
    await page.waitForTimeout(1000);
    console.log('Switched to Candidate B successfully.');
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'iteration_2_1_candidate_b_overview.png') });

    // Switch back to Candidate 1 (Shreekrishna)
    await candidateSwitcherBtn.click();
    await page.waitForTimeout(400);
    const candidateAItem = page.locator('button[role="menuitem"]:has-text("Shreekrishna")');
    await candidateAItem.click();
    await page.waitForTimeout(1000);
    console.log('Switched back to Candidate 1 (Shreekrishna).');
  }

  await context.close();
  await browser.close();

  console.log('\n--- CareerOS 2.9.0 Iteration 2.1 Overview Audit Complete ---');
}

runOverviewAudit().catch(err => {
  console.error('Overview audit failed with error:', err);
  process.exit(1);
});
